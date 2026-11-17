"""Linha de comando.

  fraudguard triar --casos data/cases.jsonl --saida runs/hoje
  fraudguard reaplicar --casos data/cases.jsonl --resultados runs/hoje/resultados.json --saida runs/v2
  fraudguard sinais --casos data/cases.jsonl
  fraudguard verificar-mensagem "Me passa o código" --distancia 1500
"""
from __future__ import annotations

import argparse
import json
import sys

from .policy import MENSAGENS_PADRAO
from .signals import FORTE, MODERADO, calcular_sinais


def _cmd_triar(a) -> int:
    from .config import make_llm
    from .llm import QuotaExceeded
    from .report import gravar
    from .triage import carregar_casos, triar

    casos = carregar_casos(a.casos)
    try:
        resultado = triar(casos, make_llm(a.modelo), lote=a.lote)
    except QuotaExceeded as e:
        print(f"Erro: {e}", file=sys.stderr)
        return 2
    out = gravar(resultado, a.saida)
    st = {}
    for d in resultado["decisoes"]:
        st[d["status"]] = st.get(d["status"], 0) + 1
    print(f"{len(casos)} casos triados em {resultado['segundos']} s com {resultado['uso']['chamadas']} chamadas.")
    print("  " + ", ".join(f"{k}: {v}" for k, v in sorted(st.items())))
    for aviso in resultado["avisos"]:
        print(f"  aviso: {aviso}")
    print(f"Relatório: {out / 'relatorio.md'}")
    return 0


def _cmd_reaplicar(a) -> int:
    from pathlib import Path

    from .report import gravar
    from .triage import carregar_casos, reaplicar

    anterior = json.loads(Path(a.resultados).read_text(encoding="utf-8"))
    resultado = reaplicar(carregar_casos(a.casos), anterior)
    out = gravar(resultado, a.saida)
    print(f"Política reaplicada a {len(resultado['decisoes'])} casos, sem chamadas ao LLM. Relatório: "
          f"{out / 'relatorio.md'}")
    return 0


def _cmd_sinais(a) -> int:
    from .triage import carregar_casos

    for caso in carregar_casos(a.casos):
        sinais = calcular_sinais(caso)
        print(f"{caso['id']}: " + (", ".join(f"{s.id} ({s.forca})" for s in sinais) or "nenhum sinal"))
    return 0


def _cmd_mensagem(a) -> int:
    """Checagem em tempo real de uma mensagem do chat, só com regras (milissegundos, sem custo de LLM)."""
    caso = {
        "id": "mensagem",
        "pedido": {"valor": a.valor, "pagamento": a.pagamento, "contestacoes_90d": 0},
        "eventos": [],
        "chat": [{"autor": a.autor, "texto": a.texto, "distancia_entregador_m": a.distancia}],
        "relato": "",
    }
    sinais = [s for s in calcular_sinais(caso) if s.forca in (FORTE, MODERADO)]
    alerta = None
    ids = {s.id for s in sinais}
    if ids & {"suporte_fora_do_canal", "pedido_de_dados_ou_pix"}:
        alerta = MENSAGENS_PADRAO["falso_atendente"]
    if "link_externo" in ids:
        alerta = MENSAGENS_PADRAO["link_malicioso"]
    if "codigo_pedido_longe" in ids:
        alerta = MENSAGENS_PADRAO["codigo_entrega"]
    if ids & {"cobranca_em_pedido_pago", "valor_acima_do_pedido"}:
        alerta = MENSAGENS_PADRAO["cobranca_extra"]
    print(json.dumps({"sinais": [s.to_dict() for s in sinais], "alerta_ao_cliente": alerta},
                     ensure_ascii=False, indent=1))
    return 1 if alerta else 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="fraudguard", description="Triagem de denúncias de fraude em delivery com IA.")
    sub = p.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("triar", help="classifica os casos com o LLM e aplica a política de decisão")
    t.add_argument("--casos", required=True, help="arquivo JSONL com os casos")
    t.add_argument("--saida", required=True, help="pasta onde gravar resultados.json e relatorio.md")
    t.add_argument("--modelo", default=None, help="modelo Gemini (padrão: GEMINI_MODEL ou gemini-3.5-flash-lite)")
    t.add_argument("--lote", type=int, default=8, help="casos por chamada ao LLM (padrão: 8)")
    t.set_defaults(fn=_cmd_triar)

    r = sub.add_parser("reaplicar", help="reaplica a política sobre um resultados.json já gravado (sem LLM)")
    r.add_argument("--casos", required=True)
    r.add_argument("--resultados", required=True, help="resultados.json gerado por `fraudguard triar`")
    r.add_argument("--saida", required=True)
    r.set_defaults(fn=_cmd_reaplicar)

    s = sub.add_parser("sinais", help="mostra os sinais determinísticos de cada caso (sem LLM)")
    s.add_argument("--casos", required=True)
    s.set_defaults(fn=_cmd_sinais)

    m = sub.add_parser("verificar-mensagem", help="checa uma mensagem do chat em tempo real, só com regras")
    m.add_argument("texto")
    m.add_argument("--autor", default="entregador", choices=["entregador", "cliente", "desconhecido"])
    m.add_argument("--pagamento", default="app", choices=["app", "na_entrega"])
    m.add_argument("--valor", type=float, default=0.0, help="valor do pedido em reais")
    m.add_argument("--distancia", type=int, default=None, help="distância do entregador ao endereço, em metros")
    m.set_defaults(fn=_cmd_mensagem)

    a = p.parse_args(argv)
    if getattr(a, "lote", 1) < 1:
        p.error("--lote deve ser maior que zero")
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
