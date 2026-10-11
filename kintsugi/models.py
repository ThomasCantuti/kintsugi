"""LLM client: any OpenAI-compatible endpoint (OpenRouter, NVIDIA), fallback chain, cost meter.

Tests swap `chat` for `scripted([...])`, so no tokens are spent.
"""
import json
from dataclasses import dataclass, field

from openai import AsyncOpenAI

from . import config


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: str  # raw JSON string, exactly as the model produced it


@dataclass
class Reply:
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    model: str = ""
    cost: float = 0.0
    tokens: int = 0
    fallbacks: int = 0  # how many models in the chain failed before this one answered


class BudgetExceeded(RuntimeError):
    pass


spent = 0.0  # process-wide cost meter (USD)
_client: AsyncOpenAI | None = None


def client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(base_url=config.LLM_BASE_URL, api_key=config.LLM_API_KEY, max_retries=2, timeout=120)
    return _client


def _cost(usage) -> float:
    if usage is None:
        return 0.0
    extra = getattr(usage, "model_extra", None) or {}
    return float(getattr(usage, "cost", None) or extra.get("cost") or 0.0)


async def chat(messages: list[dict], tools: list[dict] | None = None, model: str | None = None,
               fallbacks: list[str] | None = None, temperature: float = 0.0, json_mode: bool = False) -> Reply:
    """One completion. Tries `model`, then each fallback, on any provider error."""
    global spent
    if spent >= config.BUDGET_USD:
        raise BudgetExceeded(f"spent ${spent:.2f} of ${config.BUDGET_USD}")
    chain = [model or config.AGENT_MODEL] + (config.AGENT_FALLBACK_MODELS if fallbacks is None else fallbacks)
    error: Exception | None = None
    for i, m in enumerate(dict.fromkeys(chain)):
        kw: dict = {"model": m, "messages": messages, "temperature": temperature}
        if tools:
            kw["tools"] = tools
        if json_mode:
            kw["response_format"] = {"type": "json_object"}
        try:
            r = await client().chat.completions.create(**kw)
            if not r.choices:
                raise RuntimeError(f"{m}: empty response")
        except Exception as e:  # provider down, rate limited, bad request for this model...
            error = e
            continue
        msg = r.choices[0].message
        cost = _cost(r.usage)
        spent += cost
        calls = [ToolCall(c.id, c.function.name, c.function.arguments or "{}") for c in (msg.tool_calls or [])]
        return Reply(msg.content or "", calls, m, cost, r.usage.total_tokens if r.usage else 0, i)
    raise error or RuntimeError("no model in chain")


async def chat_json(messages: list[dict], model: str | None = None) -> dict:
    """Completion parsed as a JSON object (tolerates ```json fences and surrounding prose)."""
    r = await chat(messages, model=model, fallbacks=[], json_mode=True)
    return parse_json(r.text)


def parse_json(text: str) -> dict:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise
        return json.loads(text[start:end + 1])


async def embed(texts: list[str]) -> list[list[float]]:
    r = await client().embeddings.create(model=config.EMBED_MODEL, input=texts)
    return [d.embedding for d in r.data]


def scripted(replies: list):
    """Deterministic stand-in for `chat`: returns each Reply (or callable(messages) -> Reply) in order."""
    queue = list(replies)

    async def fake_chat(messages, tools=None, **kw) -> Reply:
        r = queue.pop(0)
        return r(messages) if callable(r) else r

    return fake_chat
