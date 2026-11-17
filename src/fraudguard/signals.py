"""Sinais determinísticos: o que o código consegue verificar sem depender do modelo.

Os sinais servem para três coisas:
1. conferir a classificação do LLM (um "sem fraude" com sinal forte vai para revisão humana);
2. exigir prova objetiva antes de acusar alguém (ex.: contestação suspeita só com telemetria);
3. servir de baseline: o benchmark compara "só regras" contra "LLM + regras".

O modelo nunca vê estes sinais, para que a checagem cruzada seja independente.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass
from urllib.parse import urlparse

# Domínios oficiais da plataforma fictícia. Em produção viria de configuração.
DOMINIOS_OFICIAIS = ("deliveryapp.example",)

# Distância a partir da qual o código de entrega não deveria ser pedido ou validado.
DIST_LONGE_M = 300
# Distância até a qual consideramos que a entrega aconteceu no endereço.
DIST_PORTA_M = 50

FORTE, MODERADO, CONTRA = "forte", "moderado", "contraevidencia"


@dataclass(frozen=True)
class Sinal:
    id: str
    forca: str  # forte | moderado | contraevidencia
    descricao: str
    evidencia: str

    def to_dict(self) -> dict:
        return asdict(self)


def normalizar(texto: str) -> str:
    """Minúsculas, sem acentos e com espaços colapsados (usado em regex e na checagem de citações)."""
    t = unicodedata.normalize("NFKD", texto or "")
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    t = t.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
    return re.sub(r"\s+", " ", t).strip().lower()


_RE_DINHEIRO = re.compile(r"\b(taxa|maquin\w*|cobr\w*|pag(ar|amento|ue|a)\b|pix|cartao|gorjeta obrigat\w*)")
_RE_PEDIDO_PAGO_OK = re.compile(r"(nao precisa pagar|ja esta pago|esta pago|ja foi pago)")
_RE_VALOR = re.compile(r"r\$\s?(\d{1,3}(?:\.\d{3})+(?:,\d{2})?|\d+(?:,\d{2})?)")
_RE_URL = re.compile(
    r"(?:https?://|www\.)[^\s)\]]+|\b[a-z0-9][a-z0-9-]*(?:\.[a-z0-9-]+)*\.(?:com|net|org|top|xyz|online|click|ly|br|info|site|link|example)(?:/[^\s)\]]*)?",
)
_RE_TELEFONE = re.compile(r"\(?\b\d{2}\)?\s?9\d{4}-?\d{4}\b")
_RE_DADOS = re.compile(
    r"(pix|cvv|codigo de seguranca|senha|numero do cartao|dados bancarios|codigo que chegou|por sms|cpf)"
)
_RE_SUPORTE = re.compile(r"(suporte|atendimento|atendente|central)")
_RE_CONTATO_FORA = re.compile(r"(whatsapp|ligar|ligacao|contato|telefone)")
_RE_INJECAO = re.compile(
    r"(ignore (as |suas |todas as )?(instrucoes|regras)|classifique (este caso )?como|marque como|"
    r"\[?sistema:|system:|assistente de ia|aprove o reembolso|you are now|ignore previous)"
)


def _valor_brl(s: str) -> float:
    return float(s.replace(".", "").replace(",", "."))


def dominio(url: str) -> str:
    u = url if url.startswith(("http://", "https://")) else "http://" + url
    host = (urlparse(u).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def eh_oficial(dom: str) -> bool:
    return any(dom == d or dom.endswith("." + d) for d in DOMINIOS_OFICIAIS)


def links(texto: str) -> list[str]:
    return [m.group(0).rstrip(".,;:!?'\"") for m in _RE_URL.finditer(normalizar(texto))]


def calcular_sinais(caso: dict) -> list[Sinal]:
    pedido = caso.get("pedido", {})
    pago_no_app = pedido.get("pagamento") == "app"
    valor = float(pedido.get("valor", 0))
    sinais: list[Sinal] = []

    # Telemetria do código de entrega
    for ev in caso.get("eventos", []):
        if ev.get("tipo") == "codigo_validado" and "distancia_m" in ev:
            d = ev["distancia_m"]
            if d > DIST_LONGE_M:
                sinais.append(Sinal("codigo_validado_longe", FORTE,
                                    "Código de entrega validado longe do endereço",
                                    f"codigo_validado a {d} m do endereço às {ev.get('hora')}"))
            elif d <= DIST_PORTA_M:
                sinais.append(Sinal("entrega_no_endereco", CONTRA,
                                    "Código validado no endereço do cliente",
                                    f"codigo_validado a {d} m do endereço às {ev.get('hora')}"))

    for msg in caso.get("chat", []):
        autor = msg.get("autor")
        texto = msg.get("texto", "")
        t = normalizar(texto)
        dist = msg.get("distancia_entregador_m")
        de_terceiro = autor != "cliente"

        if de_terceiro and "codigo" in t and dist is not None and dist > DIST_LONGE_M:
            sinais.append(Sinal("codigo_pedido_longe", FORTE,
                                "Entregador pediu o código antes de chegar",
                                f"{autor} a {dist} m: \"{texto}\""))

        if de_terceiro and pago_no_app and _RE_DINHEIRO.search(t) and not _RE_PEDIDO_PAGO_OK.search(t):
            sinais.append(Sinal("cobranca_em_pedido_pago", MODERADO,
                                "Menção a pagamento em pedido já pago no app",
                                f"{autor}: \"{texto}\""))

        if de_terceiro and not pago_no_app:
            for m in _RE_VALOR.finditer(t):
                v = _valor_brl(m.group(1))
                if v > valor + 1:
                    sinais.append(Sinal("valor_acima_do_pedido", FORTE,
                                        "Valor cobrado acima do total do pedido",
                                        f"pedido de R$ {valor:.2f}, cobrado R$ {v:.2f}: \"{texto}\""))

        if de_terceiro and _RE_DADOS.search(t):
            sinais.append(Sinal("pedido_de_dados_ou_pix", MODERADO,
                                "Pedido de pix ou dado sensível no chat",
                                f"{autor}: \"{texto}\""))

        if de_terceiro and _RE_SUPORTE.search(t) and (_RE_CONTATO_FORA.search(t) or _RE_TELEFONE.search(t)):
            sinais.append(Sinal("suporte_fora_do_canal", FORTE,
                                "Atendimento oferecido fora do app",
                                f"{autor}: \"{texto}\""))

    # Links em qualquer texto (chat ou relato)
    textos = [m.get("texto", "") for m in caso.get("chat", [])] + [caso.get("relato", "")]
    vistos = set()
    for texto in textos:
        for url in links(texto):
            dom = dominio(url)
            if dom and not eh_oficial(dom) and dom not in vistos:
                vistos.add(dom)
                sinais.append(Sinal("link_externo", FORTE, "Link fora dos domínios oficiais", url))

    # Tentativa de injeção de prompt em qualquer texto controlado por terceiros
    for texto in textos:
        if _RE_INJECAO.search(normalizar(texto)):
            sinais.append(Sinal("tentativa_de_injecao", FORTE,
                                "Texto tenta dar ordens ao sistema de IA", texto[:160]))
            break

    if int(pedido.get("contestacoes_90d", 0)) >= 3:
        sinais.append(Sinal("historico_de_contestacoes", MODERADO,
                            "Cliente com 3 ou mais contestações em 90 dias",
                            f"{pedido['contestacoes_90d']} contestações em 90 dias"))
    return sinais


def tem(sinais: list[Sinal], *ids: str) -> bool:
    return any(s.id in ids for s in sinais)


def fortes(sinais: list[Sinal]) -> list[Sinal]:
    return [s for s in sinais if s.forca == FORTE]
