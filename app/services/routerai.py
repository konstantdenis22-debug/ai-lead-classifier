from __future__ import annotations

import time
from typing import Any, Optional

from openai import AsyncOpenAI, APIError, APITimeoutError, AuthenticationError, RateLimitError

from app.config import get_settings


class RouterAIError(Exception):
    """Base error for RouterAI interactions."""

    def __init__(self, code: str, message: str, http_status: Optional[int] = None):
        self.code = code
        self.message = message
        self.http_status = http_status
        super().__init__(message)


class RouterAIClient:
    def __init__(self) -> None:
        settings = get_settings()
        self.model = settings.MODEL_ID
        self.timeout = settings.REQUEST_TIMEOUT
        self.temperature = settings.TEMPERATURE
        self.client = AsyncOpenAI(
            api_key=settings.ROUTERAI_API_KEY,
            base_url=settings.ROUTERAI_BASE_URL,
            timeout=self.timeout,
        )

    async def chat(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> tuple[str, float, int, Optional[dict]]:
        """
        Returns: (content, latency_ms, http_status, usage_dict)
        """
        start = time.perf_counter()
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=self.temperature,
                response_format={"type": "json_object"},
            )
            latency_ms = (time.perf_counter() - start) * 1000
            content = response.choices[0].message.content or ""
            usage = None
            if response.usage:
                usage = {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                }
            return content, latency_ms, 200, usage

        except AuthenticationError as e:
            raise RouterAIError("ROUTERAI_AUTH_ERROR", str(e), 401) from e
        except RateLimitError as e:
            raise RouterAIError("ROUTERAI_RATE_LIMIT", str(e), 429) from e
        except APITimeoutError as e:
            raise RouterAIError("ROUTERAI_TIMEOUT", str(e), 408) from e
        except APIError as e:
            status = getattr(e, "status_code", 503)
            if status >= 500:
                raise RouterAIError("ROUTERAI_UNAVAILABLE", str(e), status) from e
            raise RouterAIError("INTERNAL_ERROR", str(e), status) from e
        except Exception as e:
            raise RouterAIError("INTERNAL_ERROR", str(e)) from e
