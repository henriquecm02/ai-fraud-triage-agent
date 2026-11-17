"""Fila de revisão para a equipe de prevenção a fraudes.

  streamlit run app/streamlit_app.py

Lê uma saída de `fraudguard triar` (padrão: a execução real em examples/execucao_gemini) e os casos
originais. O analista vê o chat, a telemetria, os sinais e as evidências, e aprova ou recusa as
ações que pedem aprovação. As decisões ficam na sessão e podem ser baixadas em JSON.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
import streamlit as st

RAIZ = Path(__file__).resolve().parents[1]
RESULTADOS = Path(os.getenv("FRAUDGUARD_RESULTADOS", RAIZ / "examples" / "execucao_gemini" / "resultados.json"))
CASOS = Path(os.getenv("FRAUDGUARD_CASOS", RAIZ / "data" / "cases.jsonl"))

ROTULOS = {
    "cobranca_extra": "Cobrança extra na entrega",
    "codigo_entrega": "Código de entrega obtido antes da entrega",
    "falso_atendente": "Falso atendente",
    "link_malicioso": "Link malicioso",
    "contestacao_suspeita": "Contestação suspeita",
    "sem_fraude": "Sem fraude",
    "indefinida": "Indefinida",
}
STATUS = {"revisao_humana": "Revisão humana", "acao_recomendada": "Ação recomendada", "encerrado": "Encerrado"}
ORDEM = {"alta": 0, "media": 1, "baixa": 2}

st.set_page_config(page_title="Triagem de fraudes", layout="wide")
st.title("Triagem de denúncias de fraude")

if not RESULTADOS.exists():
    st.error(f"Arquivo de resultados não encontrado: {RESULTADOS}. Rode `fraudguard triar` primeiro.")
    st.stop()

resultado = json.loads(RESULTADOS.read_text(encoding="utf-8"))
casos = {}
if CASOS.exists():
    for linha in CASOS.read_text(encoding="utf-8").splitlines():
        if linha.strip():
            c = json.loads(linha)
            casos[c["id"]] = c
# Revisão humana primeiro: é o que depende do analista. Depois, prioridade.
decisoes = sorted(resultado["decisoes"],
                  key=lambda d: (d["status"] != "revisao_humana", ORDEM[d["prioridade"]], d["id"]))
aprovacoes = st.session_state.setdefault("aprovacoes", {})

st.caption(f"Modelo `{resultado['modelo']}` · {resultado['casos']} casos · {resultado['segundos']} s · "
           f"{resultado['uso']['chamadas']} chamadas ao LLM")
c1, c2, c3 = st.columns(3)
c1.metric("Revisão humana", sum(d["status"] == "revisao_humana" for d in decisoes))
c2.metric("Ação recomendada", sum(d["status"] == "acao_recomendada" for d in decisoes))
c3.metric("Encerrados sem fraude", sum(d["status"] == "encerrado" for d in decisoes))

filtro = st.multiselect("Status", list(STATUS), default=["revisao_humana", "acao_recomendada"],
                        format_func=STATUS.get)
visiveis = [d for d in decisoes if d["status"] in filtro]
st.dataframe(pd.DataFrame([{
    "Caso": d["id"], "Prioridade": d["prioridade"], "Status": STATUS[d["status"]],
    "Categoria": ROTULOS.get(d["categoria"], d["categoria"]), "Confiança do modelo": d["confianca_modelo"],
    "Sinais que apoiam": ", ".join(d["sinais_que_apoiam"]) or "—",
} for d in visiveis]), hide_index=True, width="stretch")

if not visiveis:
    st.info("Nenhum caso com esse filtro.")
    st.stop()

escolhido = st.selectbox("Abrir caso", [d["id"] for d in visiveis])
d = next(x for x in visiveis if x["id"] == escolhido)
caso = casos.get(escolhido, {})

st.subheader(f"{d['id']} · {ROTULOS.get(d['categoria'], d['categoria'])}")
if d["motivos_revisao"]:
    st.warning("Por que está em revisão: " + "; ".join(d["motivos_revisao"]))

esq, dir_ = st.columns(2)
with esq:
    st.markdown("**Relato do cliente**")
    st.write(caso.get("relato", "—"))
    st.markdown("**Chat do pedido**")
    for m in caso.get("chat", []):
        st.text(f"{m['hora']} {m['autor']} ({m.get('distancia_entregador_m', '?')} m): {m['texto']}")
    if not caso.get("chat"):
        st.caption("Sem mensagens no chat.")
    st.markdown("**Telemetria**")
    for ev in caso.get("eventos", []):
        dist = f" a {ev['distancia_m']} m" if "distancia_m" in ev else ""
        st.text(f"{ev['hora']} {ev['tipo']}{dist}")
with dir_:
    st.markdown("**Evidências citadas pelo modelo (conferidas no texto)**")
    for ev in d["evidencias"]:
        st.markdown(f"- {ev['fonte']}: “{ev['trecho']}”")
    for ev in d["evidencias_descartadas"]:
        st.markdown(f"- ~~{ev.get('trecho', '')}~~ (não existe no caso, descartada)")
    if not d["evidencias"] and not d["evidencias_descartadas"]:
        st.caption("Nenhuma.")
    st.markdown("**Sinais calculados por código**")
    for s in d["sinais"]:
        st.markdown(f"- `{s['id']}` ({s['forca']}): {s['evidencia']}")
    st.markdown("**Justificativa do modelo**")
    st.write(d["justificativa"] or "—")
    st.markdown("**Mensagem ao cliente**")
    st.info(d["mensagem_cliente"])

st.markdown("**Ações**")
for a in d["acoes"]:
    chave = f"{d['id']}:{a['acao']}"
    if a["automatica"]:
        st.markdown(f"- {a['acao']}: automática")
        continue
    col_a, col_b, col_c = st.columns([3, 1, 1])
    col_a.markdown(f"- {a['acao']}: **{aprovacoes.get(chave, 'aguardando aprovação')}**")
    if col_b.button("Aprovar", key="ok-" + chave):
        aprovacoes[chave] = "aprovada"
        st.rerun()
    if col_c.button("Recusar", key="no-" + chave):
        aprovacoes[chave] = "recusada"
        st.rerun()

st.download_button("Baixar decisões do analista (JSON)", json.dumps(aprovacoes, ensure_ascii=False, indent=1),
                   file_name="decisoes_analista.json", mime="application/json")
