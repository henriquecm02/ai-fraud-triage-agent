"""Conjunto ruidoso: erros de digitação, vários golpes no mesmo caso e telemetria ausente."""
import json

from test_policy import LONGE, PORTA, clf

from fraudguard.baseline import categorias_por_regras
from fraudguard.classifier import classificar
from fraudguard.llm import ScriptedLLM
from fraudguard.metrics import avaliar_multirrotulo
from fraudguard.policy import decidir
from fraudguard.signals import calcular_sinais, corrigir_digitacao
from fraudguard.triage import carregar_casos

from conftest import RAIZ
from test_signals import caso


def test_correcao_de_digitacao_generica():
    assert corrigir_digitacao("me passa o cogido") == "me passa o codigo"  # letras trocadas
    assert corrigir_digitacao("a makininha") == "a maquininha"
    assert corrigir_digitacao("centra de atendimeto") == "central de atendimento"
    # palavras comuns que não são palavra-chave não mudam
    for palavra in ("colocar", "cadastro", "mandei", "obrigado", "pedido"):
        assert corrigir_digitacao(palavra) == palavra


def test_codigo_com_erro_de_digitacao_vira_sinal():
    c = caso(chat=[("entregador", "me passa o cogido q to xegando", 1900)], eventos=LONGE)
    assert "codigo_pedido_longe" in {s.id for s in calcular_sinais(c)}


def test_telemetria_ausente_vira_sinal_e_bloqueia_acusar_cliente():
    c = caso(chat=[], eventos=[{"hora": "20:00", "tipo": "pedido_criado"}], relato="Não recebi.")
    sinais = calcular_sinais(c)
    assert "telemetria_ausente" in {s.id for s in sinais}
    r = decidir(c, sinais, clf("contestacao_suspeita", [("relato", "Não recebi")]))
    assert r["status"] == "revisao_humana"


def test_golpe_secundario_apontado_pelo_modelo_soma_acoes_com_aprovacao():
    c = caso(chat=[("entregador", "tem taxa de R$ 9,90 na maquininha", 100)], eventos=PORTA,
             relato="Depois mandaram o link estorno-delivery.top")
    item = clf("cobranca_extra", [("chat", "tem taxa de R$ 9,90 na maquininha")])
    item["outras_categorias"] = ["link_malicioso"]
    r = decidir(c, calcular_sinais(c), item)
    assert [o["categoria"] for o in r["outras_categorias"]] == ["link_malicioso"]
    acoes = {a["acao"]: a["automatica"] for a in r["acoes"]}
    assert acoes["solicitar_derrubada_do_dominio"] is False  # derrubar domínio pede aprovação
    assert acoes["estornar_cobranca_indevida"] is False


def test_cliente_nunca_e_acusado_como_golpe_secundario():
    c = caso(chat=[("entregador", "tem taxa na maquininha", 100)], eventos=PORTA, relato="cobraram a mais")
    item = clf("cobranca_extra", [("chat", "tem taxa na maquininha")]) | {"outras_categorias": ["contestacao_suspeita"]}
    assert decidir(c, calcular_sinais(c), item)["outras_categorias"] == []


def test_classificador_filtra_outras_categorias_invalidas():
    c = caso(chat=[("entregador", "oi", 10)])
    resposta = {"casos": [{"id": c["id"], "categoria": "cobranca_extra", "confianca": "alta", "evidencias": [],
                           "justificativa": "x", "mensagem_cliente": "x", "texto_tenta_instruir_a_ia": False,
                           "outras_categorias": ["link_malicioso", "inexistente", "cobranca_extra", "sem_fraude",
                                                 "link_malicioso"]}]}
    out, _, _ = classificar([c], ScriptedLLM(lambda p, s: resposta))
    assert out[c["id"]]["outras_categorias"] == ["link_malicioso"]


def test_conjunto_ruidoso_e_gabarito_consistentes():
    casos = carregar_casos(RAIZ / "data" / "cases_ruidosos.jsonl")
    gab = json.loads((RAIZ / "data" / "ground_truth_ruidosos.json").read_text(encoding="utf-8"))
    assert {c["id"] for c in casos} == set(gab)
    assert all(g["categoria"] in g["categorias"] for g in gab.values())
    assert sum(len(g["categorias"]) > 1 for g in gab.values()) == 3
    assert any(not any(e["tipo"] == "codigo_validado" for e in c["eventos"]) for c in casos)


def test_metrica_multirrotulo():
    gab = {"A": {"categoria": "x", "categorias": ["x", "y"]}, "B": {"categoria": "x", "categorias": ["x"]}}
    m = avaliar_multirrotulo({"A": {"x"}, "B": {"x"}}, gab)
    assert m["golpes_encontrados"] == "1/2" and m["casos_com_todos_os_golpes"] == "0/1"


def test_baseline_multirrotulo_soma_golpes_com_sinal():
    c = caso(chat=[("entregador", "tem taxa na maquininha, estorno em estorno-delivery.top", 100)], eventos=PORTA)
    assert categorias_por_regras(calcular_sinais(c)) >= {"cobranca_extra", "link_malicioso"}
