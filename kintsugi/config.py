"""Settings from env (.env). Empty values fall back to the defaults below."""
import os

from dotenv import load_dotenv

load_dotenv()


def _env(key: str, default: str = "") -> str:
    return os.getenv(key) or default


def _list(key: str, default: str = "") -> list[str]:
    return [x.strip() for x in _env(key, default).split(",") if x.strip()]


# Empty = local dev deployment (`atlas local`), else the Atlas Sandbox URI
MONGODB_URI = _env("MONGODB_URI", "mongodb://localhost:59283/?directConnection=true")
DB_NAME = _env("DB_NAME", "kintsugi")

TELEGRAM_BOT_TOKEN = _env("TELEGRAM_BOT_TOKEN")
OWNER_TELEGRAM_ID = int(_env("OWNER_TELEGRAM_ID", "0"))

LLM_BASE_URL = _env("LLM_BASE_URL", "https://openrouter.ai/api/v1")
LLM_API_KEY = _env("LLM_API_KEY", _env("OPENROUTER_API_KEY"))
AGENT_MODEL = _env("AGENT_MODEL", "nvidia/nemotron-3-super-120b-a12b:free")
AGENT_FALLBACK_MODELS = _list(
    "AGENT_FALLBACK_MODELS", "nvidia/nemotron-3.5-lightning:free,nvidia/nemotron-3-ultra-550b-a55b:free"
)
SUPERVISOR_MODEL = _env("SUPERVISOR_MODEL", "nvidia/nemotron-3-ultra-550b-a55b:free")
FRONTIER_MODEL = _env("FRONTIER_MODEL", "anthropic/claude-sonnet-5.5")
# Voyage via an Atlas model API key (https://ai.mongodb.com/v1) or a voyageai.com key (https://api.voyageai.com/v1).
# EMBED_API_KEY empty → embeddings come from the LLM endpoint instead (EMBED_MODEL must be one it serves).
EMBED_API_KEY = _env("EMBED_API_KEY")
EMBED_BASE_URL = _env("EMBED_BASE_URL", "https://ai.mongodb.com/v1")
EMBED_MODEL = _env("EMBED_MODEL", "voyage-4-lite" if EMBED_API_KEY else "nvidia/nemotron-3-embed-1b:free")
BUDGET_USD = float(_env("BUDGET_USD", "5"))
# Raindrop watches live turns (bot server only; evals, gate and evolve never send). Empty key = off.
RAINDROP_WRITE_KEY = _env("RAINDROP_WRITE_KEY")
RAINDROP_EVENT_CAP = 800  # free Hobby plan: 1,000 events/month, and ingestion stops for the month at the cap
# Query API key (dashboard → Settings → API Keys → Query SDK). Set = Raindrop-flagged live turns go to the learner.
RAINDROP_QUERY_API_KEY = _env("RAINDROP_QUERY_API_KEY")
EXA_API_KEY = _env("EXA_API_KEY")
AGENT_REASONING = _env("AGENT_REASONING", "on") != "off"  # off: Nemotron answers without hidden reasoning (~5x faster)
# Signals that send a live turn to the learner (compared without case, spaces, "_" or "-")
RAINDROP_FLAGS = {"userfrustration", "attemptedpromptinjection", "requestexecutionneedscorrection"}  # 2 presets + our custom signal (Raindrop named it)

TIMEZONE = "America/Los_Angeles"
LESSONS_TOP_K = 8  # context policy: max learned rules/policies retrieved per message
PORT = int(_env("PORT", "8000"))
