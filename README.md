# papich_bench

A small, pluggable benchmark for **search engines, LLMs, and web-search agents**.
Ask a set of obscure questions, let any number of "answerers" respond, and have
an LLM judge score each answer on two axes:

- **Found it** — did the answer surface what you actually wanted?
- **Truthful** — is the answer factually correct (no hallucination)?

The whole point is that **adding a new engine or model is one small file or a few
config lines** — Tavily today, Perplexity, Google, or something else tomorrow.

```
Question ──▶ [ Answerer(s) ] ──▶ Answer ──▶ [ LLM Judge ] ──▶ found / truthful score
             tavily, perplexity,                              (vs. your reference
             google, llm_websearch, …                         answer)
```

## Install

Requires **Python 3.11+**.

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env        # then fill in the keys you have
```

## Run

```bash
# Validate config + dataset (no API calls)
papich-bench validate

# Run the benchmark defined in configs/default.yaml
papich-bench run

# Run just one engine over a dataset, and also emit an HTML report
papich-bench run --answerers llm_direct --dataset datasets/papich.yaml --html report.html

# Re-render a saved results file without spending any API budget
papich-bench report results/20260828-120000.json --format html --out report.html

# See what's available
papich-bench list-answerers
```

Each run writes a full `results/<timestamp>.json` and prints a leaderboard:

```
        Leaderboard
 #  Answerer     Score  Found  Truthful  Errors  Latency
 1  duckduckgo     71%   1.57      1.29       0     1.8s
 2  llm_direct     54%   1.14      1.00       0     2.3s
```

## Zero-cost quickstart

The defaults cost **nothing** and need exactly **one free signup**. The judge and
the `llm_direct` baseline run on a free [OpenRouter](https://openrouter.ai) model,
and the `duckduckgo` search contestant needs no key at all.

1. Get a free key at <https://openrouter.ai/keys>.
2. `cp .env.example .env`, then set `OPENAI_API_KEY=<your OpenRouter key>` (the
   base URL already defaults to OpenRouter).
3. Run the default config — a plain LLM vs. a real search engine, judged for free:

   ```bash
   papich-bench run --html report.html
   ```

Swap the free model for any other zero-price id in `configs/default.yaml`; browse
current ones at <https://openrouter.ai/models?max_price=0> (free ids change often
— a `404` means the id is gone, so pick another).

### Free-tier rate limits (important)

OpenRouter's **free tier caps `:free` models at ~50 requests/day and ~20/minute**
(shared across all free models). A single benchmark run makes several calls per
step (answer + judge, plus a summarizer for search engines), so a few runs can
exhaust the daily cap and you'll see `429` / "not judged" rows. The run already
backs off and retries on `429`, and caching means completed answers/judgements
are never re-billed — but a hard daily cap it cannot beat. Options:

- **Park $10 of credits on OpenRouter once.** This raises the free-model cap to
  **1000/day**, and `:free` models still cost **$0** (the balance isn't drawn
  down). Best "still free, actually usable" fix.
- **Run a local [Ollama](https://ollama.com)** — truly unlimited and free. Set
  `OPENAI_BASE_URL=http://localhost:11434/v1` and use a local model id.
- **Use [Groq](https://console.groq.com)'s free tier** (separate quota).
- **Just wait** — the daily cap resets at UTC midnight; a re-run reuses cached
  answers and only spends quota on the steps still missing a judgement.
- **Spend less per run**: fewer questions/answerers, or a single answerer
  (`--answerers duckduckgo`).

## Can I use Anthropic / Perplexity / Google for free?

For low volume, mostly yes — the trick is which door you use:

| Provider | Free path | In this project |
| --- | --- | --- |
| **Google (search)** | **Custom Search JSON API** = 100 queries/day free (needs a free API key + a Programmable Search Engine id). | `google_cse` answerer — set `GOOGLE_API_KEY` + `GOOGLE_CSE_ID`. |
| **Google (LLM)** | Gemini API free tier, via its OpenAI-compatible endpoint. | `openai` backend with `OPENAI_BASE_URL=…/v1beta/openai`. |
| **DuckDuckGo** | No key, ever. | `duckduckgo` answerer (default). |
| **Perplexity** | No free API tier — **but Perplexity Pro** includes **$5/month** of API credits, enough for small runs. | `perplexity` answerer with your `PERPLEXITY_API_KEY`. |
| **Anthropic (Claude)** | No standing free tier; new API accounts sometimes get a small trial credit. Your Claude.ai / Claude Code **subscription is not usable as an API key.** | `llm_websearch` / `anthropic` judge with `ANTHROPIC_API_KEY`. |

So: DuckDuckGo and OpenRouter/Gemini/Groq/Ollama are truly free; Google search is
free at 100/day; Perplexity is free only via a Pro subscription's credits; and
Anthropic effectively needs paid (or trial) API credit.

## Keeping it free — the knobs

- **Judge & LLM answerers:** the `openai` backend points at `OPENAI_BASE_URL`.
  Free options: **OpenRouter** `:free` models (default), **Groq**'s free tier,
  **Gemini**'s free tier, or a fully-local **Ollama** (`http://localhost:11434/v1`, no key).
- **`duckduckgo`:** a real search engine with **no key** — free with just the
  OpenRouter signup (used to summarize the results).
- **`llm_direct`:** an LLM answering from memory — no search key. A useful
  baseline: does search actually beat a plain LLM on obscure questions?
- **`google_cse`:** free Google results (100/day). `tavily` has a free tier too.
- **Caching:** every answer and judgement is cached under `.cache/`, so re-runs
  and report tweaks cost nothing. Use `--no-cache` to force a fresh run.

## Where questions, answers, and criteria live

Your benchmark content lives in one place: a **dataset YAML** under `datasets/`
(the default is `datasets/papich.yaml`). Each item bundles the question, the
correct answer, and the grading criteria:

```yaml
- id: my-question                       # stable slug (used for caching + report)
  prompt: What obscure thing do you want to know?
  reference_answer: The known-correct answer — the "truth" the judge checks against.
  wanted: The single key fact that counts as "found it" (the found-it criterion).
  tags: [whatever]                      # optional labels for slicing results
```

- **Answers / ground truth** → `reference_answer`. The judge scores *truthful*
  against this.
- **Criteria for "did they find what I wanted"** → `wanted`. The judge scores
  *found* against this.
- Keep **multiple datasets** (e.g. `datasets/mytopic.yaml`) and pick one per run
  with `--dataset datasets/mytopic.yaml`.
- The **global grading rubric** (how strict the judge is, what the two scores
  mean) lives in the judge prompt: `src/papich_bench/judge.py` and the field
  descriptions in `src/papich_bench/models.py` (`Judgement`). Edit those to
  change judging behavior for *every* question at once.

Validate your dataset any time without spending anything: `papich-bench validate`.

## Branching flows (conditional follow-up questions)

An item can be a **flow** instead of a single question: ask Q1, and depending on
the answer either stop or branch to a follow-up. Each step lists named
`branches`; after the step is answered, an LLM **router** picks the branch whose
`if` condition the answer matches and follows its `then` (a step id, or `stop`).
Follow-ups see the earlier turns (conversation is carried by default —
`carry_context: true`), so search engines and LLMs both handle them uniformly.

```yaml
- id: my-flow
  steps:
    - id: q1
      prompt: What was the first product sold on Amazon?
      reference_answer: A book by Douglas Hofstadter.
      wanted: names the specific book
      branches:
        - if: the answer already names the exact book title
          then: stop
        - if: it says a book but not which title
          then: q2            # ask the follow-up
        - if: the answer is wrong
          then: stop
    - id: q2
      prompt: It was a book — which exact title?
      reference_answer: Fluid Concepts and Creative Analogies
      wanted: the exact title
```

Every step is still judged normally, so a flow's steps all count toward the
leaderboard; the report shows each answerer's full transcript and which branch it
took. The shipped `datasets/papich.yaml` is a real three-step flow you can run:

```bash
papich-bench run --dataset datasets/papich.yaml
```

Single questions and flows can be mixed in the same dataset file. Turn off
context-carrying (answer each step fresh) with `carry_context: false` in the config.

## Add a new answerer (search engine, LLM, or agent)

Drop a module in `src/papich_bench/answerers/`, implement `_answer`, and register
it. That's the whole contract:

```python
from papich_bench.answerers.base import Answerer
from papich_bench.config import Settings
from papich_bench.models import AnswerContent, Citation
from papich_bench.registry import register_answerer


@register_answerer("my_engine")
class MyEngineAnswerer(Answerer):
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    @classmethod
    def from_settings(cls, settings: Settings, options: dict) -> "MyEngineAnswerer":
        return cls(settings.require("my_engine_api_key", needed_by="the 'my_engine' answerer"))

    async def _answer(self, prompt: str) -> AnswerContent:
        ...  # call your API
        return AnswerContent(text=answer, citations=[Citation(url=u) for u in urls])
```

Then import it in `src/papich_bench/answerers/__init__.py`, add any secret to
`config.Settings`, and reference `my_engine` in your config. Timing, error
capture, conversation context, and caching are handled for you by the base class
(it calls your `_answer` from `run(prompt, step_id)`).

## Layout

```
src/papich_bench/
  models.py       # pydantic types (Flow, FlowStep, Branch, Answer, Judgement, …)
  config.py       # Settings (env/secrets) + RunConfig (YAML)
  registry.py     # @register_answerer name -> class
  dataset.py      # load/validate the dataset YAML (single questions + flows)
  cache.py        # on-disk JSON cache
  answerers/      # one file per contestant (llm_direct, duckduckgo, tavily,
                  #   google_cse, google_serpapi, perplexity, llm_websearch)
  llm/            # LLMClient interface + Anthropic and OpenAI-compatible backends
  judge.py        # LLM-as-judge (found + truthful rubric)
  router.py       # LLM router that picks a flow's next branch
  runner.py       # async flow orchestration with bounded concurrency + caching
  report.py       # leaderboard + per-item transcripts (Markdown/HTML)
  cli.py          # `papich-bench` commands
```

## Development

```bash
ruff check . && ruff format --check .
mypy src
pytest            # fully offline — no keys or network needed
```

## License

MIT
