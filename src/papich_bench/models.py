"""Core data models shared across the pipeline.

Everything that flows between the dataset, answerers, judge, runner, and report
is a pydantic model defined here, so serialization to/from the results JSON and
the on-disk cache is uniform and validated.

A benchmark item is a **Flow**: one or more steps. A plain single question is
just a one-step flow (the dataset loader builds it for you). Each step can carry
**branches** — an LLM router picks which one the answer matches to decide the
next step (or ``stop``), which is how conditional follow-up questions work.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SCORE_MIN = 0
SCORE_MAX = 2
SCORE_LABELS = {0: "no", 1: "partial", 2: "yes"}

STOP = "stop"


class Citation(BaseModel):
    """A source an answerer cited, when it exposes one."""

    url: str
    title: str | None = None


class Branch(BaseModel):
    """A conditional edge out of a step: if the answer matches, go to ``then``."""

    model_config = ConfigDict(populate_by_name=True)

    condition: str = Field(
        alias="if",
        description="A natural-language description of the answer case, matched by the router LLM.",
    )
    then: str = Field(description="The next step id to ask, or 'stop' to end the flow.")


class FlowStep(BaseModel):
    """One question within a flow — the gradeable unit."""

    id: str
    prompt: str
    reference_answer: str = Field(
        description="The known-correct answer the judge grades truthfulness against."
    )
    wanted: str = Field(
        default="",
        description="What 'found what I wanted' means for this step — the key fact(s) wanted.",
    )
    branches: list[Branch] = Field(
        default_factory=list,
        description="Conditional next-steps. Empty means the flow stops after this step.",
    )


class Flow(BaseModel):
    """A benchmark item: a start step plus optional branching follow-ups."""

    id: str
    steps: list[FlowStep]
    start: str | None = Field(default=None, description="Start step id (defaults to the first).")
    tags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_graph(self) -> Flow:
        if not self.steps:
            raise ValueError(f"flow {self.id!r} has no steps")
        ids = [s.id for s in self.steps]
        if len(ids) != len(set(ids)):
            raise ValueError(f"flow {self.id!r} has duplicate step ids")
        valid = set(ids) | {STOP}
        for step in self.steps:
            for branch in step.branches:
                if branch.then not in valid:
                    raise ValueError(
                        f"flow {self.id!r} step {step.id!r} branches to unknown step "
                        f"{branch.then!r}"
                    )
        if self.start is not None and self.start not in ids:
            raise ValueError(f"flow {self.id!r} start {self.start!r} is not a step id")
        return self

    def step(self, step_id: str) -> FlowStep | None:
        return next((s for s in self.steps if s.id == step_id), None)

    def start_step(self) -> FlowStep:
        if self.start is not None:
            found = self.step(self.start)
            if found is not None:
                return found
        return self.steps[0]


class AnswerContent(BaseModel):
    """The payload an answerer produces, before run-level metadata is attached."""

    text: str
    citations: list[Citation] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)


class Answer(BaseModel):
    """A single answerer's response to a single step."""

    answerer: str
    step_id: str
    text: str = ""
    citations: list[Citation] = Field(default_factory=list)
    latency_s: float = 0.0
    error: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict, exclude=True)

    @property
    def ok(self) -> bool:
        return self.error is None


class Judgement(BaseModel):
    """The judge's verdict on one answer. Also used verbatim as the judge's
    structured-output schema, so its field docs are the grading rubric."""

    found_score: int = Field(
        ge=SCORE_MIN,
        le=SCORE_MAX,
        description="Did the answer surface what the asker wanted? "
        "0 = missed it, 1 = partially, 2 = fully.",
    )
    found_reasoning: str = Field(description="One or two sentences justifying found_score.")
    truthful_score: int = Field(
        ge=SCORE_MIN,
        le=SCORE_MAX,
        description="Is the answer factually correct vs. the reference? "
        "0 = false/hallucinated, 1 = partly correct, 2 = fully correct.",
    )
    truthful_reasoning: str = Field(description="One or two sentences justifying truthful_score.")

    @property
    def combined(self) -> int:
        """Sum of both axes, 0-4. Used for ranking."""
        return self.found_score + self.truthful_score


class StepResult(BaseModel):
    """One answered (and judged) step within a flow run. ``next`` is the step
    the router chose after it, or ``stop``."""

    step_id: str
    prompt: str
    answer: Answer
    judgement: Judgement | None = None
    judge_error: str | None = None
    next: str = STOP


class FlowRun(BaseModel):
    """One answerer's walk through one flow."""

    answerer: str
    steps: list[StepResult] = Field(default_factory=list)


class FlowResult(BaseModel):
    """All answerers' runs for one flow."""

    flow: Flow
    runs: list[FlowRun] = Field(default_factory=list)


class LeaderboardRow(BaseModel):
    """Aggregated scores for one answerer across every step of the run.

    Every step lands in exactly one bucket: ``n`` judged (the means average over
    these), ``n_unjudged`` answered but the judge failed, or ``n_errors`` where
    the answerer itself errored.
    """

    answerer: str
    n: int
    n_unjudged: int
    n_errors: int
    mean_found: float
    mean_truthful: float
    mean_latency_s: float

    @property
    def n_total(self) -> int:
        return self.n + self.n_unjudged + self.n_errors

    @property
    def score_pct(self) -> float:
        """Combined score as a 0-100 percentage of the maximum possible."""
        return 100.0 * (self.mean_found + self.mean_truthful) / (2 * SCORE_MAX)


class RunReport(BaseModel):
    """The full, serializable result of one benchmark run."""

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    dataset: str
    judge_model: str
    answerers: list[str]
    results: list[FlowResult] = Field(default_factory=list)

    @field_validator("created_at")
    @classmethod
    def _tz_aware(cls, v: datetime) -> datetime:
        return v if v.tzinfo else v.replace(tzinfo=UTC)

    def _steps_for(self, answerer: str) -> list[StepResult]:
        return [
            step
            for fr in self.results
            for run in fr.runs
            if run.answerer == answerer
            for step in run.steps
        ]

    def leaderboard(self) -> list[LeaderboardRow]:
        """Aggregate per-answerer scores over every step, ranked best-first."""
        rows: list[LeaderboardRow] = []
        for name in self.answerers:
            steps = self._steps_for(name)
            judged = [s.judgement for s in steps if s.judgement is not None]
            n_errors = sum(1 for s in steps if not s.answer.ok)
            rows.append(
                LeaderboardRow(
                    answerer=name,
                    n=len(judged),
                    n_unjudged=len(steps) - len(judged) - n_errors,
                    n_errors=n_errors,
                    mean_found=_mean(j.found_score for j in judged),
                    mean_truthful=_mean(j.truthful_score for j in judged),
                    mean_latency_s=_mean(s.answer.latency_s for s in steps),
                )
            )
        return sorted(rows, key=lambda r: r.score_pct, reverse=True)


def _mean(values: Any) -> float:
    items = list(values)
    return sum(items) / len(items) if items else 0.0
