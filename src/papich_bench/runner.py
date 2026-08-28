"""Orchestration: run every answerer over every question, then judge each answer.

Concurrency is bounded by a semaphore; answerer responses and judgements are
cached on disk so re-runs are free. A failing answerer records an error and
does not abort the run.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass

from papich_bench.answerers.base import Answerer
from papich_bench.cache import JSONCache
from papich_bench.config import AnswererSpec, LLMSpec, RunConfig, Settings
from papich_bench.dataset import load_dataset
from papich_bench.judge import Judge
from papich_bench.llm import build_llm
from papich_bench.models import Answer, JudgedAnswer, Judgement, Question, QuestionResult, RunReport
from papich_bench.registry import get_answerer

ProgressFn = Callable[[str], None]


@dataclass
class _Contestant:
    spec: AnswererSpec
    answerer: Answerer


def build_contestants(config: RunConfig, settings: Settings) -> list[_Contestant]:
    """Instantiate every answerer named in the config."""
    contestants = []
    for spec in config.answerers:
        cls = get_answerer(spec.name)
        contestants.append(_Contestant(spec, cls.from_settings(settings, spec.options)))
    return contestants


async def run_benchmark(
    config: RunConfig,
    settings: Settings,
    *,
    use_cache: bool = True,
    on_progress: ProgressFn | None = None,
) -> RunReport:
    """Run the full benchmark and return a populated ``RunReport``."""
    questions = load_dataset(config.dataset)
    cache = JSONCache(config.cache_dir, enabled=use_cache)
    contestants = build_contestants(config, settings)
    judge = Judge(build_llm(config.judge, settings))
    sem = asyncio.Semaphore(max(1, config.concurrency))

    def progress(msg: str) -> None:
        if on_progress:
            on_progress(msg)

    try:
        results = await asyncio.gather(
            *(
                _process_question(q, contestants, judge, config.judge, cache, sem, progress)
                for q in questions
            )
        )
    finally:
        for c in contestants:
            await c.answerer.aclose()
        await judge.aclose()

    return RunReport(
        dataset=config.dataset,
        judge_model=judge.model,
        answerers=[c.spec.name for c in contestants],
        results=list(results),
    )


async def _process_question(
    question: Question,
    contestants: list[_Contestant],
    judge: Judge,
    judge_spec: LLMSpec,
    cache: JSONCache,
    sem: asyncio.Semaphore,
    progress: ProgressFn,
) -> QuestionResult:
    judged = await asyncio.gather(
        *(
            _answer_and_judge(question, c, judge, judge_spec, cache, sem, progress)
            for c in contestants
        )
    )
    return QuestionResult(question=question, answers=list(judged))


async def _answer_and_judge(
    question: Question,
    contestant: _Contestant,
    judge: Judge,
    judge_spec: LLMSpec,
    cache: JSONCache,
    sem: asyncio.Semaphore,
    progress: ProgressFn,
) -> JudgedAnswer:
    async with sem:
        answer = await _get_answer(question, contestant, cache)
    progress(f"answered {question.id} / {contestant.spec.name}")

    result = JudgedAnswer(answer=answer)
    if answer.ok and answer.text.strip():
        async with sem:
            try:
                result.judgement = await _get_judgement(question, answer, judge, judge_spec, cache)
            except Exception as exc:
                result.judge_error = f"{type(exc).__name__}: {exc}"
        progress(f"judged {question.id} / {contestant.spec.name}")
    return result


async def _get_answer(question: Question, contestant: _Contestant, cache: JSONCache) -> Answer:
    key = {
        "answerer": contestant.spec.name,
        "options": contestant.spec.options,
        "qid": question.id,
        "prompt": question.prompt,
    }
    cached = cache.get("answers", key)
    if cached is not None:
        return Answer.model_validate(cached)

    answer = await contestant.answerer.run(question)
    if answer.ok:  # never cache failures — let them be retried next run
        cache.set("answers", key, answer.model_dump(mode="json"))
    return answer


async def _get_judgement(
    question: Question, answer: Answer, judge: Judge, judge_spec: LLMSpec, cache: JSONCache
) -> Judgement:
    key = {
        "judge_backend": judge_spec.backend,
        "judge_model": judge_spec.model,
        "qid": question.id,
        "answerer": answer.answerer,
        "answer_text": answer.text,
    }
    cached = cache.get("judgements", key)
    if cached is not None:
        return Judgement.model_validate(cached)

    judgement = await judge.judge(question, answer)
    cache.set("judgements", key, judgement.model_dump(mode="json"))
    return judgement
