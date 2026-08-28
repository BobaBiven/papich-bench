"""Flow router: given a step's answer, decide which branch to follow.

Each step declares named branches ("if the answer names the book -> stop; if it
only says a book -> ask q2"). The router asks an LLM which branch's condition the
candidate answer best matches, and returns that branch's target step id (or
``stop``). Steps with no branches always stop.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from papich_bench.llm.base import LLMClient
from papich_bench.models import STOP, Answer, FlowStep

ROUTER_SYSTEM = (
    "You route a branching questionnaire. Given a question, the candidate's answer, "
    "and a numbered list of possible answer-cases, choose the single case that best "
    "describes the candidate's answer. If none of the cases fit, choose -1. "
    "Judge only which case matches; do not grade correctness."
)


class RouterDecision(BaseModel):
    branch_index: int = Field(
        description="0-based index of the matching case, or -1 if none of them fit."
    )
    reason: str = Field(description="One short sentence on why this case matches.")


def _build_prompt(step: FlowStep, answer: Answer) -> str:
    cases = "\n".join(f"[{i}] {b.condition}" for i, b in enumerate(step.branches))
    candidate = answer.text.strip() or "(the answerer returned no answer)"
    return (
        f"QUESTION:\n{step.prompt}\n\n"
        f"CANDIDATE ANSWER:\n{candidate}\n\n"
        f"POSSIBLE CASES:\n{cases}\n\n"
        "Which case (by number) best describes the candidate answer? Use -1 if none fit."
    )


class Router:
    """Wraps an ``LLMClient`` to choose a step's outgoing branch."""

    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    async def route(self, step: FlowStep, answer: Answer) -> str:
        if not step.branches:
            return STOP
        decision = await self._llm.structured(
            system=ROUTER_SYSTEM,
            prompt=_build_prompt(step, answer),
            schema=RouterDecision,
        )
        idx = decision.branch_index
        if 0 <= idx < len(step.branches):
            return step.branches[idx].then
        return STOP
