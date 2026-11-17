import json

import pytest

from fraudguard.report import gravar
from fraudguard.triage import triar

from conftest import RAIZ, llm_oraculo

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest
APP = str(RAIZ / "app" / "streamlit_app.py")


@pytest.fixture
def resultados(tmp_path, casos, gabarito, monkeypatch):
    r = triar(casos, llm_oraculo(gabarito))
    gravar(r, tmp_path)
    monkeypatch.setenv("FRAUDGUARD_RESULTADOS", str(tmp_path / "resultados.json"))
    return r


def test_app_mostra_fila_e_aprova_acao(resultados):
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception
    assert [str(m.value) for m in at.metric] == ["3", "37", "8"]
    botoes = [b for b in at.button if b.key and b.key.startswith("ok-")]
    assert botoes, "o caso aberto deveria ter ação que pede aprovação"
    acao = botoes[0].key.split(":", 1)[1]
    botoes[0].click().run()
    assert not at.exception
    assert any(acao in m.value and "aprovada" in m.value for m in at.markdown)


def test_app_sem_resultados_mostra_erro(tmp_path, monkeypatch):
    monkeypatch.setenv("FRAUDGUARD_RESULTADOS", str(tmp_path / "nao_existe.json"))
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert at.error and "não encontrado" in at.error[0].value


def test_exemplo_versionado_e_valido():
    exemplo = RAIZ / "examples" / "execucao_gemini" / "resultados.json"
    if not exemplo.exists():
        pytest.skip("exemplo real ainda não gerado")
    r = json.loads(exemplo.read_text(encoding="utf-8"))
    assert r["casos"] == len(r["decisoes"]) == 48
    assert r["modelo"].startswith("gemini")
