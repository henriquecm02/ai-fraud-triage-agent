"""Baseline só com regras: classifica a partir dos sinais determinísticos, sem LLM.

Serve de comparação no benchmark. Não lê o relato do cliente (só links e injeção nele),
o que é justamente a parte em que um modelo de linguagem deveria ajudar.
"""
from __future__ import annotations

from .signals import Sinal, tem


def classificar_por_regras(sinais: list[Sinal]) -> str:
    if tem(sinais, "suporte_fora_do_canal"):
        return "falso_atendente"
    if tem(sinais, "link_externo"):
        return "link_malicioso"
    if tem(sinais, "codigo_validado_longe", "codigo_pedido_longe"):
        return "codigo_entrega"
    if tem(sinais, "valor_acima_do_pedido", "cobranca_em_pedido_pago"):
        return "cobranca_extra"
    if tem(sinais, "pedido_de_dados_ou_pix"):
        return "falso_atendente"
    if tem(sinais, "entrega_no_endereco") and tem(sinais, "historico_de_contestacoes"):
        return "contestacao_suspeita"
    return "sem_fraude"
