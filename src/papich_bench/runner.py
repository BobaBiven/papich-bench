"""Orchestration: walk every flow with every answerer, judging each step.

For each (flow, answerer) pair the runner walks the flow: ask the step (with
prior turns folded in when ``carry_context``), judge the answer, then let the
router pick the next step from the step's branches — until a branch says ``stop``
(or a step has no branches). Concurrency is bounded by a semaphore, and answers,
judgements, and routing decisions are cached on disk so re-runs are free.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass

from papich_bench.answerers.base import Answerer, Turn, contextualize
from papich_bench.cache import JSONCache
from papich_bench.config import AnswererSpec, LLMSpec, RunConfig, Settings
from papich_bench.dataset import load_dataset
from papich_bench.judge import Judge
from papich_bench.llm import build_llm
from papich_bench.models import (
    STOP,
    Answer,
    Flow,
    FlowResult,
    FlowRun,
    FlowStep,
    Judgement,
    RunReport,
    StepResult,
)
from papich_bench.registry import get_answerer
from papich_bench.router import Router

ProgressFn = Callable[[str], None]

MAX_STEPS = 12


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
    flows = load_dataset(config.dataset)
    cache = JSONCache(config.cache_dir, enabled=use_cache)
    contestants = build_contestants(config, settings)
    llm = build_llm(config.judge, settings)
    judge, router = Judge(llm), Router(llm)
    sem = asyncio.Semaphore(max(1, config.concurrency))

    def progress(msg: str) -> None:
        if on_progress:
            on_progress(msg)

    try:
        results = await asyncio.gather(
            *(
                _process_flow(flow, contestants, judge, router, config, cache, sem, progress)
                for flow in flows
            )
        )
    finally:
        for c in contestants:
            await c.answerer.aclose()
        await llm.aclose()

    return RunReport(
        dataset=config.dataset,
        judge_model=judge.model,
        answerers=[c.spec.display_name for c in contestants],
        results=list(results),
    )


async def _process_flow(
    flow: Flow,
    contestants: list[_Contestant],
    judge: Judge,
    router: Router,
    config: RunConfig,
    cache: JSONCache,
    sem: asyncio.Semaphore,
    progress: ProgressFn,
) -> FlowResult:
    runs = await asyncio.gather(
        *(
            _run_flow_for_contestant(flow, c, judge, router, config, cache, sem, progress)
            for c in contestants
        )
    )
    return FlowResult(flow=flow, runs=list(runs))


async def _run_flow_for_contestant(
    flow: Flow,
    contestant: _Contestant,
    judge: Judge,
    router: Router,
    config: RunConfig,
    cache: JSONCache,
    sem: asyncio.Semaphore,
    progress: ProgressFn,
) -> FlowRun:
    """Walk one flow with one answerer until a branch says ``stop``, a step
    repeats, or ``MAX_STEPS`` is hit. A judge failure is recorded on the step;
    a routing failure ends the flow."""
    history: list[Turn] = []
    visited: set[str] = set()
    steps_out: list[StepResult] = []

    step: FlowStep | None = flow.start_step()
    while step is not None and step.id not in visited and len(steps_out) < MAX_STEPS:
        visited.add(step.id)
        prompt = contextualize(step.prompt, history) if config.carry_context else step.prompt

        async with sem:
            answer = await _get_answer(prompt, step, contestant, cache)
        progress(f"answered {flow.id}/{step.id} · {contestant.spec.display_name}")

        result = StepResult(step_id=step.id, prompt=step.prompt, answer=answer)
        usable = answer.ok and bool(answer.text.strip())
        if usable:
            async with sem:
                try:
                    result.judgement = await _get_judgement(
                        step, answer, judge, config.judge, cache
                    )
                except Exception as exc:
                    result.judge_error = f"{type(exc).__name__}: {exc}"
            if step.branches:
                async with sem:
                    try:
                        result.next = await _get_route(step, answer, router, config.judge, cache)
                    except Exception:
                        result.next = STOP
            history.append(Turn(question=step.prompt, answer=answer.text))

        steps_out.append(result)
        if result.next == STOP:
            break
        step = flow.step(result.next)

    return FlowRun(answerer=contestant.spec.display_name, steps=steps_out)


async def _get_answer(
    prompt: str, step: FlowStep, contestant: _Contestant, cache: JSONCache
) -> Answer:
    """Failed answers are never cached, so the next run retries them."""
    key = {
        "answerer": contestant.spec.name,
        "options": contestant.spec.options,
        "prompt": prompt,
    }
    cached = cache.get("answers", key)
    if cached is not None:
        return Answer.model_validate(cached)

    answer = await contestant.answerer.run(prompt, step.id)
    if answer.ok:
        cache.set("answers", key, answer.model_dump(mode="json"))
    return answer


async def _get_judgement(
    step: FlowStep, answer: Answer, judge: Judge, judge_spec: LLMSpec, cache: JSONCache
) -> Judgement:
    key = {
        "judge": f"{judge_spec.backend}:{judge_spec.model}",
        "prompt": step.prompt,
        "reference": step.reference_answer,
        "wanted": step.wanted,
        "answer_text": answer.text,
    }
    cached = cache.get("judgements", key)
    if cached is not None:
        return Judgement.model_validate(cached)

    judgement = await judge.judge(step, answer)
    cache.set("judgements", key, judgement.model_dump(mode="json"))
    return judgement


async def _get_route(
    step: FlowStep, answer: Answer, router: Router, judge_spec: LLMSpec, cache: JSONCache
) -> str:
    key = {
        "router": f"{judge_spec.backend}:{judge_spec.model}",
        "prompt": step.prompt,
        "branches": [{"if": b.condition, "then": b.then} for b in step.branches],
        "answer_text": answer.text,
    }
    cached = cache.get("routes", key)
    if cached is not None and isinstance(cached.get("next"), str):
        return str(cached["next"])

    next_id = await router.route(step, answer)
    cache.set("routes", key, {"next": next_id})
    return next_id
