import json
from collections import Counter

import generate_cases
from conftest import RAIZ


def test_gerador_e_deterministico_e_bate_com_os_arquivos(casos, gabarito):
    c1, g1 = generate_cases.build()
    c2, g2 = generate_cases.build()
    assert c1 == c2 and g1 == g2
    assert c1 == casos, "data/cases.jsonl desatualizado: rode python data/generate_cases.py"
    assert g1 == gabarito


def test_conjunto_balanceado_e_ids_unicos(casos, gabarito):
    assert len(casos) == 48
    assert len({c["id"] for c in casos}) == 48
    assert set(gabarito) == {c["id"] for c in casos}
    assert set(Counter(g["categoria"] for g in gabarito.values()).values()) == {8}


def test_gabarito_nao_vaza_para_os_casos(casos):
    texto = (RAIZ / "data" / "cases.jsonl").read_text(encoding="utf-8")
    assert "categoria" not in texto and "cenario" not in texto
    for c in casos:
        assert set(c) == {"id", "pedido", "eventos", "chat", "relato"}


def test_injecoes_marcadas_no_gabarito(gabarito):
    injecoes = [g for g in gabarito.values() if g["injecao"]]
    assert len(injecoes) == 3
    assert {g["categoria"] for g in injecoes} == {"cobranca_extra", "falso_atendente", "link_malicioso"}


def test_placeholders_preenchidos(casos):
    bruto = json.dumps(casos, ensure_ascii=False)
    assert "{valor" not in bruto


def test_conjunto_dificil_deterministico_e_separado(casos):
    from fraudguard.triage import carregar_casos

    from conftest import RAIZ as raiz

    c1, g1 = generate_cases.build(generate_cases.CENARIOS_DIFICEIS, prefixo="H", seed=generate_cases.SEED + 1)
    assert c1 == carregar_casos(raiz / "data" / "cases_dificeis.jsonl")
    assert g1 == json.loads((raiz / "data" / "ground_truth_dificeis.json").read_text(encoding="utf-8"))
    assert len(c1) == 17 and all(c["id"].startswith("H") for c in c1)
    # nenhum texto do conjunto difícil repete um texto do principal
    principal = {c["relato"] for c in casos}
    assert not principal & {c["relato"] for c in c1}
