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
papich-bench run --answerers tavily --dataset datasets/obscure.yaml --html report.html

# Re-render a saved results file without spending any API budget
papich-bench report results/20260828-120000.json --format html --out report.html

# See what's available
papich-bench list-answerers
```

Each run writes a full `results/<timestamp>.json` and prints a leaderboard:

```
        Leaderboard
 #  Answerer     Score  Found  Truthful  Errors  Latency
 1  tavily         71%   1.57      1.29       0     1.1s
 2  llm_direct     54%   1.14      1.00       0     2.3s
```

## Zero-cost quickstart

The defaults cost **nothing**. Both the judge and the `llm_direct` contestant run
on a free [OpenRouter](https://openrouter.ai) model (DeepSeek).

1. Get a free key at <https://openrouter.ai/keys>.
2. In `.env`, set `OPENAI_API_KEY=<your OpenRouter key>` (the base URL already
   defaults to OpenRouter).
3. Smallest possible run — one signup, no search key, just the LLM baseline:

   ```bash
   papich-bench run --answerers llm_direct
   ```

4. To also compare a real search engine, get a free [Tavily](https://app.tavily.com)
   key, add `TAVILY_API_KEY` to `.env`, and run the full default config:

   ```bash
   papich-bench run --html report.html
   ```

Swap the free model for any other zero-price id (e.g. `z-ai/glm-4.5-air:free`) in
`configs/default.yaml`; browse them at <https://openrouter.ai/models?max_price=0>.

## Keeping it free — the knobs

- **Judge & LLM answerers:** the `openai` backend points at `OPENAI_BASE_URL`.
  Free options: **OpenRouter** `:free` models (default), **Groq**'s free tier, or
  a fully-local **Ollama** (`http://localhost:11434/v1`, no key needed).
- **`llm_direct`:** an LLM answering from memory — no search key, so it's free
  on the same OpenRouter model. Also a useful baseline: does search beat a plain LLM?
- **Search:** `tavily` and `google_serpapi` (SerpAPI) both have free tiers.
  `perplexity` and `llm_websearch` (Claude) are **paid** and off by default.
- **Caching:** every answer and judgement is cached under `.cache/`, so re-runs
  and report tweaks cost nothing. Use `--no-cache` to force a fresh run.

## Add your own questions

Edit `datasets/obscure.yaml` — each item is a question, a **reference answer**
(the ground truth the judge grades against), and a `wanted` note describing what
"found it" means:

```yaml
- id: my-question
  prompt: What obscure thing do you want to know?
  reference_answer: The known-correct answer.
  wanted: The single key fact that counts as "found it".
  tags: [whatever]
```

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
`config.Settings`, and reference `my_engine` in your config. `run(question)`,
timing, error capture, and caching are handled for you by the base class.

## Layout

```
src/papich_bench/
  models.py       # pydantic types shared across the pipeline (Question, Answer, Judgement, …)
  config.py       # Settings (env/secrets) + RunConfig (YAML)
  registry.py     # @register_answerer name -> class
  dataset.py      # load/validate the questions YAML
  cache.py        # on-disk JSON cache
  answerers/      # one file per contestant (llm_direct, tavily, perplexity, google_serpapi, llm_websearch)
  llm/            # LLMClient interface + Anthropic and OpenAI-compatible backends
  judge.py        # LLM-as-judge (found + truthful rubric)
  runner.py       # async orchestration with bounded concurrency + caching
  report.py       # leaderboard + per-question Markdown/HTML
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
