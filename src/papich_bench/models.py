"""Core data models shared across the pipeline.

Everything that flows between the dataset, answerers, judge, runner, and report
is a pydantic model defined here, so serialization to/from the results JSON and
the on-disk cache is uniform and validated.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

# Scores are on a small, explicit 0-2 scale so the judge's job is unambiguous.
SCORE_MIN = 0
SCORE_MAX = 2
SCORE_LABELS = {0: "no", 1: "partial", 2: "yes"}


class Citation(BaseModel):
    """A source an answerer cited, when it exposes one."""

    url: str
    title: str | None = None


class Question(BaseModel):
    """One benchmark item, authored by hand in the dataset YAML."""

    id: str
    prompt: str
    reference_answer: str = Field(
        description="The known-correct answer the judge grades truthfulness against."
    )
    wanted: str = Field(
        default="",
        description="What 'found what I wanted' means for this question — the key "
        "fact(s) or resource the asker was really after.",
    )
    tags: list[str] = Field(default_factory=list)


class AnswerContent(BaseModel):
    """The payload an answerer produces, before run-level metadata is attached."""

    text: str
    citations: list[Citation] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)


class Answer(BaseModel):
    """A single answerer's response to a single question."""

    answerer: str
    question_id: str
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


class JudgedAnswer(BaseModel):
    """An answer paired with its judgement (None if judging failed/was skipped)."""

    answer: Answer
    judgement: Judgement | None = None
    judge_error: str | None = None


class QuestionResult(BaseModel):
    """All judged answers for one question."""

    question: Question
    answers: list[JudgedAnswer] = Field(default_factory=list)


class LeaderboardRow(BaseModel):
    """Aggregated scores for one answerer across the whole run."""

    answerer: str
    n: int
    n_errors: int
    mean_found: float
    mean_truthful: float
    mean_latency_s: float

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
    results: list[QuestionResult] = Field(default_factory=list)

    @field_validator("created_at")
    @classmethod
    def _tz_aware(cls, v: datetime) -> datetime:
        return v if v.tzinfo else v.replace(tzinfo=UTC)

    def leaderboard(self) -> list[LeaderboardRow]:
        """Aggregate per-answerer scores, ranked best-first."""
        rows: list[LeaderboardRow] = []
        for name in self.answerers:
            judged = [ja for qr in self.results for ja in qr.answers if ja.answer.answerer == name]
            scored = [ja for ja in judged if ja.judgement is not None]
            n_errors = sum(1 for ja in judged if not ja.answer.ok)
            n = len(scored)
            rows.append(
                LeaderboardRow(
                    answerer=name,
                    n=n,
                    n_errors=n_errors,
                    mean_found=_mean(ja.judgement.found_score for ja in scored),  # type: ignore[union-attr]
                    mean_truthful=_mean(ja.judgement.truthful_score for ja in scored),  # type: ignore[union-attr]
                    mean_latency_s=_mean(ja.answer.latency_s for ja in judged),
                )
            )
        return sorted(rows, key=lambda r: r.score_pct, reverse=True)


def _mean(values: Any) -> float:
    items = list(values)
    return sum(items) / len(items) if items else 0.0
