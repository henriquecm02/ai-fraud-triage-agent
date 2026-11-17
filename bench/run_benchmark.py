"""Benchmark: LLM + política contra o baseline só com regras, no conjunto com gabarito.

  python bench/run_benchmark.py                       # baseline + 1 rodada com o modelo padrão
  python bench/run_benchmark.py --modelo gemini-3.1-flash-lite --rodadas 3
  python bench/run_benchmark.py --so-baseline         # sem chamadas ao LLM

Grava bench/results/<data>_<modelo>.json (métricas e decisões) e .md (resumo).
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from fraudguard.baseline import classificar_por_regras
from fraudguard.llm import QuotaExceeded
from fraudguard.metrics import avaliar, avaliar_roteamento
from fraudguard.signals import calcular_sinais
from fraudguard.triage import carregar_casos, triar

RAIZ = Path(__file__).resolve().parents[1]


def _linha(nome: str, m: dict) -> str:
    pc = m["por_categoria"]
    return (f"| {nome} | {m['acertos']}/{m['casos']} ({m['acuracia']:.1%}) | {m['f1_macro']:.3f} | "
            f"{m['falso_alarme_em_legitimos']} | {m['golpes_classificados_como_sem_fraude']} | "
            f"{m['clientes_acusados_indevidamente']} | "
            + " | ".join(f"{pc[c]['recall']:.2f}" for c in pc) + " |")


def _relativo(caminho: str) -> str:
    p = Path(caminho).resolve()
    return str(p.relative_to(RAIZ)) if p.is_relative_to(RAIZ) else p.name


def resumo_md(res: dict) -> str:
    cats = list(res["baseline"]["por_categoria"])
    out = [f"# Benchmark {res['data']}", "",
           f"Conjunto: {res['casos']} casos sintéticos de `{res.get('conjunto', 'data/cases.jsonl')}`, "
           f"gabarito em `{res.get('gabarito', 'data/ground_truth.json')}`.", "",
           "| Abordagem | Acertos | F1 macro | Falso alarme em legítimos | Golpes vistos como sem fraude | "
           "Clientes acusados indevidamente | " + " | ".join(f"recall {c}" for c in cats) + " |",
           "|---|---|---|---|---|---|" + "---|" * len(cats),
           _linha("Só regras (baseline)", res["baseline"])]
    for i, r in enumerate(res["rodadas"], start=1):
        out.append(_linha(f"{r['modelo']} + política (rodada {i})", r["metricas"]))
    for i, r in enumerate(res["rodadas"], start=1):
        rot, m = r["roteamento"], r["metricas"]
        out += ["", f"## Rodada {i}: {r['modelo']}", "",
                f"- Tempo: {r['segundos']} s, {r['uso']['chamadas']} chamadas, "
                f"{r['uso']['tokens_entrada']} tokens de entrada e {r['uso']['tokens_saida']} de saída",
                f"- Injeções enviadas para revisão: {rot['injecoes_enviadas_para_revisao']} "
                f"(regra: {rot.get('injecoes_detectadas_por_regra', '?')}, "
                f"modelo: {rot.get('injecoes_apontadas_pelo_modelo', '?')}, "
                f"falsos positivos: {rot.get('injecoes_falsas_apontadas', '?')})",
                f"- Casos em revisão humana: {rot['casos_em_revisao_humana']}",
                f"- Erros do modelo retidos na revisão: {rot['erros_do_modelo_retidos_na_revisao']}",
                f"- Erros do modelo que passaram direto: {rot['erros_do_modelo_que_passaram_direto']} "
                f"{rot['ids_erros_que_passaram_direto'] or ''}",
                f"- Citações literais: {rot['citacoes_literais']}",
                f"- Avisos: {len(r['avisos'])}"]
        if m["erros"]:
            out += ["", "| Caso | Cenário | Esperado | Previsto |", "|---|---|---|---|"]
            out += [f"| {e['id']} | {e['cenario']} | {e['esperado']} | {e['previsto']} |" for e in m["erros"]]
    return "\n".join(out) + "\n"


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--casos", default=str(RAIZ / "data" / "cases.jsonl"))
    p.add_argument("--gabarito", default=str(RAIZ / "data" / "ground_truth.json"))
    p.add_argument("--modelo", default=None)
    p.add_argument("--lote", type=int, default=8)
    p.add_argument("--rodadas", type=int, default=1)
    p.add_argument("--so-baseline", action="store_true")
    p.add_argument("--de-resultados", nargs="*", default=[],
                   help="avalia saídas já gravadas por `fraudguard triar` (sem novas chamadas ao LLM)")
    p.add_argument("--saida", default=str(RAIZ / "bench" / "results"))
    a = p.parse_args(argv)

    casos = carregar_casos(a.casos)
    gabarito = json.loads(Path(a.gabarito).read_text(encoding="utf-8"))
    base = avaliar({c["id"]: classificar_por_regras(calcular_sinais(c)) for c in casos}, gabarito)
    res = {"data": datetime.now().strftime("%Y-%m-%d %H:%M"), "casos": len(casos),
           "conjunto": _relativo(a.casos), "gabarito": _relativo(a.gabarito), "baseline": base, "rodadas": []}

    def registrar(r: dict) -> None:
        previstos = {d["id"]: d["categoria"] for d in r["decisoes"]}
        res["rodadas"].append({
            "modelo": r["modelo"], "segundos": r["segundos"], "uso": r["uso"], "avisos": r["avisos"],
            "metricas": avaliar(previstos, gabarito),
            "roteamento": avaliar_roteamento(r["decisoes"], gabarito),
            "decisoes": r["decisoes"],
        })

    for caminho in a.de_resultados:
        registrar(json.loads(Path(caminho).read_text(encoding="utf-8")))

    if not a.so_baseline and not a.de_resultados:
        from fraudguard.config import make_llm

        llm = make_llm(a.modelo)
        for i in range(a.rodadas):
            try:
                r = triar(casos, llm, lote=a.lote)
            except QuotaExceeded as e:
                print(f"Rodada {i + 1} interrompida: {e}", file=sys.stderr)
                break
            registrar(r)

    out = Path(a.saida)
    out.mkdir(parents=True, exist_ok=True)
    rotulo = res["rodadas"][0]["modelo"] if res["rodadas"] else "baseline"
    nome = datetime.now().strftime("%Y%m%d-%H%M") + "_" + rotulo
    (out / f"{nome}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    md = resumo_md(res)
    (out / f"{nome}.md").write_text(md, encoding="utf-8")
    print(md)
    return 0 if (a.so_baseline or res["rodadas"]) else 2


if __name__ == "__main__":
    sys.exit(main())
