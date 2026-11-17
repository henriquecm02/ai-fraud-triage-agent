"""Grava a saída da triagem: JSON completo e um relatório em Markdown para a equipe."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROTULOS = {
    "cobranca_extra": "Cobrança extra na entrega",
    "codigo_entrega": "Código de entrega obtido antes da entrega",
    "falso_atendente": "Falso atendente",
    "link_malicioso": "Link malicioso",
    "contestacao_suspeita": "Contestação suspeita",
    "sem_fraude": "Sem fraude",
    "indefinida": "Indefinida",
}
ORDEM_PRIORIDADE = {"alta": 0, "media": 1, "baixa": 2}


def _md_escape(s: str) -> str:
    return s.replace("|", "\\|").replace("\n", " ")


def relatorio_md(resultado: dict) -> str:
    dec = resultado["decisoes"]
    status = Counter(d["status"] for d in dec)
    cats = Counter(d["categoria"] for d in dec)
    linhas = [
        "# Triagem de denúncias de fraude",
        "",
        f"Modelo: `{resultado['modelo']}` · {resultado['casos']} casos · {resultado['segundos']} s · "
        f"{resultado['uso']['chamadas']} chamadas ao LLM",
        "",
        "## Resumo",
        "",
        f"- Ação recomendada: **{status.get('acao_recomendada', 0)}**",
        f"- Revisão humana: **{status.get('revisao_humana', 0)}**",
        f"- Encerrados sem fraude: **{status.get('encerrado', 0)}**",
        "",
        "| Categoria | Casos |",
        "|---|---:|",
    ]
    linhas += [f"| {ROTULOS.get(c, c)} | {n} |" for c, n in cats.most_common()]

    fila = sorted([d for d in dec if d["status"] != "encerrado"],
                  key=lambda d: (d["status"] != "revisao_humana", ORDEM_PRIORIDADE[d["prioridade"]], d["id"]))
    linhas += ["", "## Fila de trabalho", "",
               "| Caso | Prioridade | Status | Categoria | Evidência | Aprovação necessária |",
               "|---|---|---|---|---|---|"]
    for d in fila:
        ev = d["evidencias"][0]["trecho"] if d["evidencias"] else "—"
        aprov = ", ".join(a["acao"] for a in d["acoes"] if not a["automatica"]) or "—"
        st = "revisão humana" if d["status"] == "revisao_humana" else "ação recomendada"
        linhas.append(f"| {d['id']} | {d['prioridade']} | {st} | {ROTULOS.get(d['categoria'], d['categoria'])} | "
                      f"{_md_escape(ev[:90])} | {aprov} |")

    revisao = [d for d in dec if d["status"] == "revisao_humana"]
    if revisao:
        linhas += ["", "## Por que foram para revisão", ""]
        for d in revisao:
            linhas.append(f"- **{d['id']}**: " + "; ".join(d["motivos_revisao"]))
    if resultado.get("avisos"):
        linhas += ["", "## Avisos", ""] + [f"- {a}" for a in resultado["avisos"]]
    return "\n".join(linhas) + "\n"


def gravar(resultado: dict, saida: str | Path) -> Path:
    out = Path(saida)
    out.mkdir(parents=True, exist_ok=True)
    (out / "resultados.json").write_text(json.dumps(resultado, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "relatorio.md").write_text(relatorio_md(resultado), encoding="utf-8")
    return out
