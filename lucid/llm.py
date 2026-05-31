from .config import PROVIDER, MODEL, API_KEY


def generate(
    system: str,
    user: str,
    *,
    model: str | None = None,
    json_mode: bool = False,
    max_tokens: int = 2048,
) -> str:
    chosen = model or MODEL
    if PROVIDER == "anthropic":
        return _call_anthropic(system, user, chosen, json_mode, max_tokens)
    return _call_openai_compat(system, user, chosen, json_mode, max_tokens)


def _call_anthropic(
    system: str,
    user: str,
    model: str,
    json_mode: bool,
    max_tokens: int,
) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=API_KEY)
    msg = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    block = msg.content[0]
    return block.text if hasattr(block, "text") else ""


def _call_openai_compat(
    system: str,
    user: str,
    model: str,
    json_mode: bool,
    max_tokens: int,
) -> str:
    from openai import OpenAI
    base_urls = {"xai": "https://api.x.ai/v1"}
    client = OpenAI(
        api_key=API_KEY,
        base_url=base_urls.get(PROVIDER),
    )
    kwargs: dict = {
        "model": model,
        "max_completion_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    resp = client.chat.completions.create(**kwargs)
    return resp.choices[0].message.content
