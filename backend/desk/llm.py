"""Gemini calls with a disk cache (same request → same answer, 0 API cost) and retry on busy errors."""
import hashlib
import json
import time

from google import genai
from google.genai import errors, types

from .config import CACHE, MODEL
from .tracing import span

_client = None
LLM_CACHE = CACHE / "llm"
LLM_CACHE.mkdir(parents=True, exist_ok=True)


class QuotaExceeded(RuntimeError):
    pass


def client():
    global _client
    if _client is None:
        _client = genai.Client(http_options=types.HttpOptions(timeout=120_000))   # never hang forever
    return _client


def generate(contents, config, model=MODEL, retries=5):
    """Returns (response, from_cache)."""
    dumped = [c.model_dump(mode="json", exclude_none=True) for c in contents]
    payload = json.dumps({"model": model,
                          "config": config.model_dump(mode="json", exclude_none=True, exclude={"tools", "response_schema"}),
                          "tools": sorted(getattr(t, "__name__", str(t)) for t in (config.tools or [])),
                          "contents": dumped},
                         sort_keys=True, default=str)
    if config.response_schema is not None:
        payload += json.dumps(config.response_schema.model_json_schema(), sort_keys=True)
    path = LLM_CACHE / (hashlib.sha256(payload.encode()).hexdigest()[:24] + ".json")
    system = config.system_instruction
    with span("gemini", as_type="generation", model=model,
              input=([{"role": "system", "content": system}] if isinstance(system, str) else []) + dumped,
              model_parameters={"temperature": config.temperature}) as gen:
        if path.exists():
            resp = types.GenerateContentResponse.model_validate_json(path.read_text())
            gen.update(output=_output(resp), metadata={"cached": True, "cached_usage": usage_of(resp)})
            return resp, True
        for attempt in range(retries):
            try:
                resp = client().models.generate_content(model=model, contents=contents, config=config)
                path.write_text(resp.model_dump_json(exclude_none=True))
                gen.update(output=_output(resp), usage_details=usage_of(resp), metadata={"cached": False, "attempts": attempt + 1})
                return resp, False
            except errors.APIError as e:
                if e.code == 429 and "PerDay" in str(e):   # daily quota: waiting won't help
                    raise QuotaExceeded(f"Daily Gemini quota used up for {model}.") from None
                if e.code not in (429, 500, 503, 504) or attempt == retries - 1:
                    raise
                time.sleep(2 ** attempt * 3)


def _output(resp):
    calls = resp.function_calls or []
    return [{"tool": c.name, "args": dict(c.args or {})} for c in calls] if calls else resp.text


def usage_of(resp):
    """Cache hits cost nothing, so their tokens go in metadata, not usage (keeps the cost chart honest)."""
    u = resp.usage_metadata
    if u is None:
        return None
    return {k: v for k, v in {"input": u.prompt_token_count, "output": u.candidates_token_count,
                              "reasoning": u.thoughts_token_count, "total": u.total_token_count}.items() if v}
