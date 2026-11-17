import json

import pytest

from fraudguard import cli, config
from fraudguard.llm import QuotaExceeded
from fraudguard.report import relatorio_md
from fraudguard.triage import carregar_casos, triar

from conftest import RAIZ, llm_oraculo


def test_verificar_mensagem_alerta_codigo_pedido_longe(capsys):
    rc = cli.main(["verificar-mensagem", "Me passa o código pra agilizar", "--distancia", "1500"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 1 and "código de entrega" in out["alerta_ao_cliente"]


def test_verificar_mensagem_legitima_nao_alerta(capsys):
    rc = cli.main(["verificar-mensagem", "Cheguei! Pode me passar o código?", "--distancia", "10"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0 and out["alerta_ao_cliente"] is None


def test_verificar_mensagem_cobranca_na_entrega(capsys):
    rc = cli.main(["verificar-mensagem", "Deu R$ 120,00 no cartão", "--pagamento", "na_entrega", "--valor", "60"])
    assert rc == 1 and "cobrança" in json.loads(capsys.readouterr().out)["alerta_ao_cliente"]


def test_triar_grava_resultados_e_relatorio(tmp_path, monkeypatch, gabarito, capsys):
    monkeypatch.setattr(config, "make_llm", lambda modelo=None: llm_oraculo(gabarito))
    rc = cli.main(["triar", "--casos", str(RAIZ / "data" / "cases.jsonl"), "--saida", str(tmp_path)])
    assert rc == 0
    r = json.loads((tmp_path / "resultados.json").read_text(encoding="utf-8"))
    assert len(r["decisoes"]) == 48
    assert "Fila de trabalho" in (tmp_path / "relatorio.md").read_text(encoding="utf-8")
    assert "48 casos triados" in capsys.readouterr().out


def test_triar_com_cota_esgotada_sai_com_erro_claro(tmp_path, monkeypatch, capsys):
    class SemCota:
        model = "x"

        def json(self, *a):
            raise QuotaExceeded("Cota do modelo x esgotada")

    monkeypatch.setattr(config, "make_llm", lambda modelo=None: SemCota())
    rc = cli.main(["triar", "--casos", str(RAIZ / "data" / "cases.jsonl"), "--saida", str(tmp_path)])
    assert rc == 2 and "esgotada" in capsys.readouterr().err


def test_lote_invalido():
    with pytest.raises(SystemExit):
        cli.main(["triar", "--casos", "x", "--saida", "y", "--lote", "0"])


def test_carregar_casos_rejeita_ids_repetidos(tmp_path):
    f = tmp_path / "c.jsonl"
    f.write_text('{"id": "A"}\n\n{"id": "A"}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="repetidos"):
        carregar_casos(f)


def test_relatorio_ordena_por_prioridade_e_escapa_tabela(casos, gabarito):
    r = triar(casos, llm_oraculo(gabarito))
    r["decisoes"][0]["evidencias"] = [{"fonte": "chat", "trecho": "a | b"}]
    r["decisoes"][0]["status"] = "acao_recomendada"
    md = relatorio_md(r)
    assert "a \\| b" in md
    fila = md.split("## Fila de trabalho")[1]
    linhas = [linha.split(" | ") for linha in fila.splitlines() if linha.startswith("| D")]
    status = [c[2] for c in linhas]
    # revisão humana primeiro; dentro de cada grupo, por prioridade
    assert status == sorted(status, key=lambda s: s != "revisão humana")
    ordem = {"alta": 0, "media": 1, "baixa": 2}
    for grupo in ("revisão humana", "ação recomendada"):
        prios = [c[1] for c in linhas if c[2] == grupo]
        assert prios == sorted(prios, key=ordem.get)
    assert "Por que foram para revisão" in md


def test_make_llm_sem_chave(monkeypatch, tmp_path):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(config.Path, "home", lambda: tmp_path)
    with pytest.raises(SystemExit, match="GEMINI_API_KEY"):
        config.make_llm()


def test_reaplicar_usa_saida_gravada_sem_chamar_o_llm(tmp_path, monkeypatch, casos, gabarito, capsys):
    from fraudguard.report import gravar

    gravar(triar(casos, llm_oraculo(gabarito)), tmp_path / "v1")

    def proibido(*a, **k):
        raise AssertionError("reaplicar não pode chamar o LLM")

    monkeypatch.setattr(config, "make_llm", proibido)
    rc = cli.main(["reaplicar", "--casos", str(RAIZ / "data" / "cases.jsonl"),
                   "--resultados", str(tmp_path / "v1" / "resultados.json"), "--saida", str(tmp_path / "v2")])
    assert rc == 0 and "sem chamadas ao LLM" in capsys.readouterr().out
    v1 = json.loads((tmp_path / "v1" / "resultados.json").read_text(encoding="utf-8"))
    v2 = json.loads((tmp_path / "v2" / "resultados.json").read_text(encoding="utf-8"))
    assert v1["decisoes"] == v2["decisoes"]


def test_reaplicar_exige_saida_crua(casos):
    from fraudguard.triage import reaplicar

    with pytest.raises(ValueError, match="classificacoes_do_modelo"):
        reaplicar(casos, {"decisoes": []})
