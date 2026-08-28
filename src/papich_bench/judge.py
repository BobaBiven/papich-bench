"""LLM-as-judge: score one answer on found-it and truthfulness.

The judge sees the question, what the asker wanted, the hand-written reference
answer, and a candidate answer, and returns a structured ``Judgement``. The
``Judgement`` schema's field descriptions (in ``models.py``) are the rubric.
"""

from __future__ import annotations

from papich_bench.llm.base import LLMClient
from papich_bench.models import Answer, Judgement, Question

JUDGE_SYSTEM = (
    "You are a rigorous, impartial benchmark judge. You grade a candidate answer "
    "against a known-correct reference answer on two independent axes:\n"
    "  * found: did the candidate surface what the asker actually wanted?\n"
    "  * truthful: is the candidate factually correct (no hallucinations)?\n"
    "Judge only the substance. Ignore style, length, and whether sources are cited. "
    "A confident but wrong answer must score truthful=0. An answer that refuses or "
    "says it could not find the information scores found=0 but is not penalized on "
    "truthfulness for honesty. Be strict and consistent."
)


def _build_prompt(question: Question, answer: Answer) -> str:
    wanted = question.wanted or "(not specified — infer from the question)"
    candidate = answer.text.strip() or "(the answerer returned no answer)"
    return (
        f"QUESTION:\n{question.prompt}\n\n"
        f"WHAT THE ASKER WANTED:\n{wanted}\n\n"
        f"REFERENCE ANSWER (ground truth):\n{question.reference_answer}\n\n"
        f"CANDIDATE ANSWER (from '{answer.answerer}'):\n{candidate}\n\n"
        "Grade the candidate answer now."
    )


class Judge:
    """Wraps an ``LLMClient`` to produce ``Judgement`` verdicts."""

    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    @property
    def model(self) -> str:
        return self._llm.model

    async def judge(self, question: Question, answer: Answer) -> Judgement:
        return await self._llm.structured(
            system=JUDGE_SYSTEM,
            prompt=_build_prompt(question, answer),
            schema=Judgement,
        )

    async def aclose(self) -> None:
        await self._llm.aclose()
