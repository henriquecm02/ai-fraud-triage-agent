"""Política de decisão: o modelo interpreta, o código confere.

Regras aplicadas sobre a classificação do LLM:
- toda evidência citada precisa existir literalmente no caso (citação inventada é descartada);
- acusar alguém exige prova: categoria de fraude sem citação confirmada vai para revisão, salvo quando
  um sinal forte de telemetria/regra apoia a mesma categoria (só vale contra golpistas, nunca contra o cliente);
- acusar o cliente de abuso (contestação suspeita) exige telemetria de entrega no endereço;
- "sem fraude" com sinal forte de golpe vai para revisão (conflito modelo x regras);
- texto que tenta dar ordens à IA força revisão humana (detectado por regex ou apontado pelo modelo);
- ações que afetam pessoas ou dinheiro (estorno, suspensão, reembolso) sempre pedem aprovação;
  só alertas e orientações ao cliente são automáticos;
- a mensagem ao cliente passa por filtro: sem links nem telefones; em revisão ou contestação,
  usa texto padrão (o cliente nunca é acusado por mensagem automática).
"""
from __future__ import annotations

import re

from .signals import _RE_TELEFONE, FORTE, Sinal, links, normalizar, tem

SUPORTE = {
    "cobranca_extra": ("cobranca_em_pedido_pago", "valor_acima_do_pedido", "pedido_de_dados_ou_pix"),
    "codigo_entrega": ("codigo_validado_longe", "codigo_pedido_longe"),
    "falso_atendente": ("suporte_fora_do_canal", "pedido_de_dados_ou_pix"),
    "link_malicioso": ("link_externo",),
    "contestacao_suspeita": ("entrega_no_endereco", "historico_de_contestacoes"),
    "sem_fraude": (),
}

# (ação, automática?) — automáticas são apenas avisos e orientações reversíveis.
ACOES = {
    "cobranca_extra": [("alertar_cliente", True), ("estornar_cobranca_indevida", False),
                       ("suspender_entregador_cautelarmente", False)],
    "codigo_entrega": [("alertar_cliente", True), ("reembolsar_pedido", False), ("investigar_entregador", False)],
    "falso_atendente": [("alertar_cliente", True), ("orientar_troca_de_senha_e_contato_com_banco", True),
                        ("denunciar_contato_falso", False)],
    "link_malicioso": [("alertar_cliente", True), ("solicitar_derrubada_do_dominio", False)],
    "contestacao_suspeita": [("revisar_historico_do_cliente", False)],
    "sem_fraude": [],
}

MENSAGENS_PADRAO = {
    "cobranca_extra": "Pedidos pagos pelo app não têm nenhuma cobrança na entrega. Não pague valores extras; "
                      "já estamos analisando a cobrança indevida.",
    "codigo_entrega": "Só informe o código de entrega quando estiver com o pedido em mãos. "
                      "Já estamos analisando o seu caso.",
    "falso_atendente": "O app nunca pede pix, senha, código de SMS ou dados do cartão por telefone, WhatsApp ou "
                       "e-mail. Se você informou algum dado, troque a senha e fale com o seu banco.",
    "link_malicioso": "Esse link não é um canal oficial do app: não clique nem informe dados. Se já informou, "
                      "troque a senha e fale com o seu banco.",
    "contestacao_suspeita": "Recebemos a sua solicitação e ela está em análise pela nossa equipe.",
    "sem_fraude": "Não encontramos indício de golpe neste pedido. Seguimos com o seu atendimento normalmente.",
    "revisao": "Recebemos o seu relato e ele está em análise pela nossa equipe.",
}

GOLPE_DE_TERCEIRO = ("cobranca_extra", "codigo_entrega", "falso_atendente", "link_malicioso")


def _limpar_trecho(t: str) -> str:
    return normalizar(t).strip(" \"'.…")


def verificar_evidencias(caso: dict, evidencias: list[dict]) -> tuple[list[dict], list[dict]]:
    """Separa citações literais (encontradas no chat ou no relato) das inventadas."""
    fontes = {"relato": [normalizar(caso.get("relato", ""))],
              "chat": [normalizar(m.get("texto", "")) for m in caso.get("chat", [])]}
    validas, invalidas = [], []
    for ev in evidencias:
        trecho = _limpar_trecho(ev.get("trecho", ""))
        achou = None
        if len(trecho) >= 3:
            for fonte in (ev.get("fonte"), "chat", "relato"):
                if fonte in fontes and any(trecho in texto for texto in fontes[fonte]):
                    achou = fonte
                    break
        if achou:
            validas.append({"fonte": achou, "trecho": ev["trecho"]})
        else:
            invalidas.append(ev)
    return validas, invalidas


def mensagem_segura(categoria: str, status: str, sugerida: str) -> tuple[str, bool]:
    """Devolve (mensagem, usou_texto_do_modelo)."""
    if status == "revisao_humana":
        return MENSAGENS_PADRAO["revisao"], False
    if categoria == "contestacao_suspeita":
        return MENSAGENS_PADRAO[categoria], False
    msg = (sugerida or "").strip()
    if not msg or len(msg) > 350 or links(msg) or _RE_TELEFONE.search(msg) or re.search(r"\bhttps?\b", msg):
        return MENSAGENS_PADRAO[categoria], False
    return msg, True


def decidir(caso: dict, sinais: list[Sinal], clf: dict | None) -> dict:
    motivos: list[str] = []
    # Duas camadas independentes: regex (não depende do modelo) e o sinalizador do próprio modelo
    # (pega formas informais que o regex não conhece).
    injecao_regex = tem(sinais, "tentativa_de_injecao")
    injecao_modelo = bool(clf and clf.get("texto_tenta_instruir_a_ia"))
    injecao = injecao_regex or injecao_modelo
    if injecao_regex:
        motivos.append("texto do caso tenta dar ordens à IA (injeção de prompt, detectada por regra)")
    elif injecao_modelo:
        motivos.append("texto do caso tenta dar ordens à IA (injeção de prompt, apontada pelo modelo)")

    if clf is None:
        categoria, confianca, validas, invalidas, sugerida, justificativa = "indefinida", "baixa", [], [], "", ""
        motivos.append("o modelo não devolveu classificação para este caso")
    else:
        categoria = clf["categoria"]
        confianca = clf["confianca"]
        sugerida = clf.get("mensagem_cliente", "")
        justificativa = clf.get("justificativa", "")
        validas, invalidas = verificar_evidencias(caso, clf.get("evidencias", []))

        if confianca == "baixa":
            motivos.append("o modelo indicou confiança baixa")
        if categoria == "sem_fraude":
            conflito = [s for s in sinais if s.forca == FORTE and s.id != "tentativa_de_injecao"]
            if conflito:
                nomes = ", ".join(sorted({s.id for s in conflito}))
                motivos.append(f"modelo diz sem fraude, mas há sinal forte: {nomes}")
        else:
            # Prova objetiva: sinal forte de telemetria/regra que apoia a mesma categoria. Vale como
            # evidência contra golpistas; para acusar o cliente, a citação literal continua obrigatória.
            prova_objetiva = categoria in GOLPE_DE_TERCEIRO and any(
                s.forca == FORTE and s.id in SUPORTE[categoria] for s in sinais)
            if not validas and invalidas:
                motivos.append("nenhuma evidência citada pelo modelo existe literalmente no caso")
            elif not validas and not prova_objetiva:
                motivos.append("o modelo não citou nenhuma evidência para sustentar a acusação")
            if categoria == "contestacao_suspeita":
                if not tem(sinais, "entrega_no_endereco"):
                    motivos.append("acusação de contestação indevida sem telemetria de entrega no endereço")
                golpe = [s.id for s in sinais if s.forca == FORTE and s.id != "tentativa_de_injecao"]
                if golpe:
                    nomes = ", ".join(sorted(set(golpe)))
                    motivos.append(f"contestação suspeita, mas há sinal forte de golpe: {nomes}")
            if categoria == "codigo_entrega" and tem(sinais, "entrega_no_endereco") and not tem(
                    sinais, "codigo_validado_longe"):
                motivos.append("telemetria mostra o código validado no endereço do cliente")

    if motivos:
        status = "revisao_humana"
    elif categoria == "sem_fraude":
        status = "encerrado"
    else:
        status = "acao_recomendada"

    if status == "revisao_humana":
        acoes = [{"acao": "revisao_por_analista", "automatica": True}] + [
            {"acao": a, "automatica": False} for a, _ in ACOES.get(categoria, [])]
        prioridade = "alta" if injecao or categoria in GOLPE_DE_TERCEIRO else "media"
    else:
        acoes = [{"acao": a, "automatica": auto} for a, auto in ACOES[categoria]]
        prioridade = {"encerrado": "baixa"}.get(status, "media" if categoria == "contestacao_suspeita" else "alta")

    mensagem, do_modelo = mensagem_segura(categoria, status, sugerida)
    apoio = [s.id for s in sinais if s.id in SUPORTE.get(categoria, ())]
    return {
        "id": caso["id"],
        "categoria": categoria,
        "confianca_modelo": confianca,
        "status": status,
        "prioridade": prioridade,
        "motivos_revisao": motivos,
        "sinais": [s.to_dict() for s in sinais],
        "sinais_que_apoiam": apoio,
        "evidencias": validas,
        "evidencias_descartadas": invalidas,
        "justificativa": justificativa,
        "acoes": acoes,
        "mensagem_cliente": mensagem,
        "mensagem_do_modelo": do_modelo,
        "injecao": {"regra": injecao_regex, "modelo": injecao_modelo},
    }
