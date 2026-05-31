import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

PROVIDER = os.getenv("LUCID_PROVIDER", "anthropic").lower()
MODEL = os.getenv("LUCID_MODEL", "claude-haiku-4-5")
PITCH_MODEL = os.getenv("LUCID_PITCH_MODEL", MODEL)

_VALID_AUDIENCES = {"developer", "manager", "non-technical", "end-user"}
AUDIENCE = os.getenv("LUCID_AUDIENCE", "developer").lower()
if AUDIENCE not in _VALID_AUDIENCES:
    sys.exit(f"[lucid] Unknown LUCID_AUDIENCE={AUDIENCE!r}. Valid: developer, manager, non-technical, end-user")

_KEY_ENV_VARS = {
    "anthropic": ("ANTHROPIC_API_KEY", "https://console.anthropic.com"),
    "openai":    ("OPENAI_API_KEY",    "https://platform.openai.com/api-keys"),
    "xai":       ("XAI_API_KEY",       "https://x.ai/api"),
}


def _resolve_key() -> str:
    if PROVIDER not in _KEY_ENV_VARS:
        sys.exit(f"[lucid] Unknown LUCID_PROVIDER={PROVIDER!r}. Valid: anthropic, openai, xai")
    env_var, url = _KEY_ENV_VARS[PROVIDER]
    key = os.getenv(env_var)
    if not key:
        sys.exit(f"[lucid] Missing {env_var} for provider={PROVIDER!r}. Get a key at {url}")
    return key


API_KEY: str = _resolve_key()
