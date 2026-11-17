"""Pipeline de triagem: sinais determinísticos -> classificação do LLM -> política de decisão."""
from __future__ import annotations

import json
import time
from pathlib import Path

from .classifier import classificar
from .llm import LLM
from .policy import decidir
from .signals import calcular_sinais


def carregar_casos(caminho: str | Path) -> list[dict]:
    casos = []
    with open(caminho, encoding="utf-8") as f:
        for n, linha in enumerate(f, start=1):
            linha = linha.strip()
            if not linha:
                continue
            caso = json.loads(linha)
            if "id" not in caso:
                raise ValueError(f"linha {n}: caso sem 'id'")
            casos.append(caso)
    ids = [c["id"] for c in casos]
    if len(ids) != len(set(ids)):
        raise ValueError("ids de casos repetidos no arquivo")
    return casos


def triar(casos: list[dict], llm: LLM, lote: int = 8) -> dict:
    t0 = time.perf_counter()
    sinais = {c["id"]: calcular_sinais(c) for c in casos}
    clf, uso, avisos = classificar(casos, llm, lote=lote)
    decisoes = [decidir(c, sinais[c["id"]], clf.get(c["id"])) for c in casos]
    return {
        "modelo": getattr(llm, "model", "?"),
        "casos": len(casos),
        "segundos": round(time.perf_counter() - t0, 2),
        "uso": {"chamadas": uso.calls, "tokens_entrada": uso.input_tokens, "tokens_saida": uso.output_tokens},
        "avisos": avisos,
        "decisoes": decisoes,
        # Saída crua do modelo: permite reaplicar a política sem novas chamadas ao LLM.
        "classificacoes_do_modelo": clf,
    }


def reaplicar(casos: list[dict], anterior: dict) -> dict:
    """Reaplica sinais e política sobre a saída crua já gravada do modelo, sem novas chamadas ao LLM."""
    clf = anterior.get("classificacoes_do_modelo")
    if clf is None:
        raise ValueError("resultado sem 'classificacoes_do_modelo': gere-o de novo com `fraudguard triar`")
    sinais = {c["id"]: calcular_sinais(c) for c in casos}
    novo = dict(anterior)
    novo["decisoes"] = [decidir(c, sinais[c["id"]], clf.get(c["id"])) for c in casos]
    return novo
