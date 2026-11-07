"""Small official DeepSeek API transport. Never logs authorization headers."""
import json
from pathlib import Path
import re
import urllib.error
import urllib.request

BASE = "https://api.deepseek.com"


class ProviderFault(RuntimeError):
    pass


class API:
    def __init__(self, credential_path):
        text = Path(credential_path).read_text(encoding="utf-8-sig").strip()
        match = re.search(r"sk-[A-Za-z0-9_-]+", text)
        if not match:
            raise ValueError("MISSING_LOCAL_API_KEY")
        self._key = match.group(0)
        self.submitted_chat_requests = 0

    def request(self, path, body=None, timeout=90):
        req = urllib.request.Request(BASE + path, data=None if body is None else json.dumps(body).encode(),
                                     headers={"Authorization": "Bearer " + self._key,
                                              "Content-Type": "application/json"})
        if body is not None:
            self.submitted_chat_requests += 1
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                value = json.load(response)
        except urllib.error.HTTPError as e:
            # Do not echo request, credential file or provider error text.
            raise ProviderFault("PROVIDER_HTTP_" + str(e.code)) from None
        except Exception as e:
            raise ProviderFault("PROVIDER_TRANSPORT_" + type(e).__name__ + "_OUTCOME_UNKNOWN_NO_RETRY") from None
        if not isinstance(value, dict) or value.get("error"):
            raise ProviderFault("PROVIDER_INVALID_OR_ERROR_RESPONSE")
        return value


def usage(raw):
    # Missing categories remain null; no cached subtraction or reasoning double count.
    details = raw.get("completion_tokens_details") or {}
    return {"totalTokens": raw.get("total_tokens"), "inputTokens": raw.get("prompt_tokens"),
            "cachedInputTokens": raw.get("prompt_cache_hit_tokens", (raw.get("prompt_tokens_details") or {}).get("cached_tokens")),
            "outputTokens": raw.get("completion_tokens"), "reasoningOutputTokens": details.get("reasoning_tokens")}


def totals(values):
    return {key: sum(v[key] for v in values) if values and all(type(v.get(key)) is int for v in values) else None
            for key in ("totalTokens", "inputTokens", "cachedInputTokens", "outputTokens", "reasoningOutputTokens")}
