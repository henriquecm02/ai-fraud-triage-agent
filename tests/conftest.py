import json
import sys
from pathlib import Path

import pytest

from fraudguard.llm import ScriptedLLM
from fraudguard.triage import carregar_casos

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "data"))  # permite "import generate_cases" nos testes


@pytest.fixture(scope="session")
def casos():
    return carregar_casos(RAIZ / "data" / "cases.jsonl")


@pytest.fixture(scope="session")
def gabarito():
    return json.loads((RAIZ / "data" / "ground_truth.json").read_text(encoding="utf-8"))


def primeiro_trecho(caso: dict) -> dict:
    """Uma citação literal do caso: a primeira mensagem do chat ou o começo do relato."""
    if caso["chat"]:
        return {"fonte": "chat", "trecho": caso["chat"][0]["texto"][:60]}
    return {"fonte": "relato", "trecho": caso["relato"][:60]}


def casos_do_prompt(prompt: str) -> list[dict]:
    corpo = prompt.split("<casos>\n", 1)[1].rsplit("\n</casos>", 1)[0]
    return [json.loads(linha) for linha in corpo.splitlines()]


def llm_oraculo(gabarito: dict, sobrescrever=None) -> ScriptedLLM:
    """LLM falso que responde com o gabarito e cita um trecho literal. `sobrescrever(id, item)` altera itens."""

    def fn(prompt, schema):
        itens = []
        for c in casos_do_prompt(prompt):
            item = {
                "id": c["id"],
                "categoria": gabarito[c["id"]]["categoria"],
                "confianca": "alta",
                "evidencias": [] if gabarito[c["id"]]["categoria"] == "sem_fraude" else [primeiro_trecho(c)],
                "justificativa": "teste",
                "mensagem_cliente": "Fique tranquilo, estamos analisando.",
                "texto_tenta_instruir_a_ia": gabarito[c["id"]]["injecao"],
            }
            if sobrescrever:
                item = sobrescrever(c["id"], item)
            if item is not None:
                itens.append(item)
        return {"casos": itens}

    return ScriptedLLM(fn)
