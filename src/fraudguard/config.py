"""Configuração via variáveis de ambiente.

Ordem de busca da chave: variável de ambiente > ./.env > ~/.config/portfolio/.env.
A chave nunca é gravada em arquivos do repositório.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

DEFAULT_MODEL = "gemini-3.5-flash-lite"


def load_env() -> None:
    load_dotenv(Path.cwd() / ".env", override=False)
    load_dotenv(Path.home() / ".config" / "portfolio" / ".env", override=False)


def make_llm(model: str | None = None):
    from .llm import GeminiLLM

    load_env()
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise SystemExit(
            "GEMINI_API_KEY não encontrada. Crie uma chave em https://aistudio.google.com e "
            "defina a variável de ambiente ou um arquivo .env (veja .env.example)."
        )
    return GeminiLLM(api_key=key, model=model or os.getenv("GEMINI_MODEL", DEFAULT_MODEL))
