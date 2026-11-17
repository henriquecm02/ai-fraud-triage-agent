"""Camada de LLM: uma interface mínima, o adaptador do Gemini e um LLM roteirizado para testes.

O pipeline nunca importa o SDK do Gemini diretamente, então os testes rodam sem rede e
trocar de provedor é implementar `json()`.
"""
from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol


class QuotaExceeded(RuntimeError):
    """Cota do provedor esgotada por um período longo (ex.: limite diário do plano gratuito)."""


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    calls: int = 0
    seconds: float = 0.0

    def add(self, other: Usage) -> None:
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.calls += other.calls
        self.seconds += other.seconds


class LLM(Protocol):
    model: str

    def json(self, system: str, prompt: str, schema: dict[str, Any]) -> tuple[dict[str, Any], Usage]: ...


class GeminiLLM:
    """Adaptador para a API do Gemini (SDK google-genai), com saída estruturada por JSON Schema."""

    def __init__(self, api_key: str, model: str, max_retries: int = 4):
        from google import genai

        self.client = genai.Client(api_key=api_key)
        self.model = model
        self.max_retries = max_retries

    def json(self, system: str, prompt: str, schema: dict[str, Any]) -> tuple[dict[str, Any], Usage]:
        from google.genai import errors, types

        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=0.0,
            response_mime_type="application/json",
            response_json_schema=schema,
        )
        delay = 2.0
        for attempt in range(self.max_retries + 1):
            try:
                t0 = time.perf_counter()
                resp = self.client.models.generate_content(model=self.model, contents=prompt, config=config)
                secs = time.perf_counter() - t0
                return json.loads(resp.text), _usage(resp, secs)
            except errors.APIError as e:
                code = getattr(e, "code", 0)
                if code == 429:
                    wait = _retry_delay(e)
                    if "PerDay" in str(e) or wait > 90:
                        raise QuotaExceeded(
                            f"Cota do modelo {self.model} esgotada (limite diário do plano gratuito). "
                            "Tente outro modelo com GEMINI_MODEL=... ou aguarde.") from e
                    delay = max(delay, wait)
                elif code not in (500, 502, 503, 504):
                    raise
                if attempt == self.max_retries:
                    raise
                time.sleep(delay)
                delay *= 2
        raise RuntimeError("inalcançável")


def _usage(resp, seconds: float) -> Usage:
    um = getattr(resp, "usage_metadata", None)
    return Usage(
        input_tokens=(getattr(um, "prompt_token_count", 0) or 0),
        output_tokens=(getattr(um, "candidates_token_count", 0) or 0) + (getattr(um, "thoughts_token_count", 0) or 0),
        calls=1,
        seconds=seconds,
    )


def _retry_delay(e) -> float:
    m = re.search(r"retry in ([\d.]+)s|'retryDelay': '(\d+)s'", str(e))
    if not m:
        return 10.0
    return float(m.group(1) or m.group(2))


class ScriptedLLM:
    """LLM falso para testes: `json_fn(prompt, schema)` gera a resposta estruturada."""

    model = "scripted"

    def __init__(self, json_fn: Callable[[str, dict], dict]):
        self.json_fn = json_fn
        self.prompts: list[str] = []

    def json(self, system, prompt, schema):
        self.prompts.append(prompt)
        return self.json_fn(prompt, schema), Usage(calls=1)
