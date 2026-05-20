from .config import PROVIDER, MODEL, API_KEY


def generate(system: str, user: str) -> str:
    if PROVIDER == "anthropic":
        return _call_anthropic(system, user)
    return _call_openai_compat(system, user)


def _call_anthropic(system: str, user: str) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=API_KEY)
    msg = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return msg.content[0].text


def _call_openai_compat(system: str, user: str) -> str:
    from openai import OpenAI
    base_urls = {"xai": "https://api.x.ai/v1"}
    client = OpenAI(
        api_key=API_KEY,
        base_url=base_urls.get(PROVIDER),
    )
    resp = client.chat.completions.create(
        model=MODEL,
        max_tokens=2048,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return resp.choices[0].message.content
