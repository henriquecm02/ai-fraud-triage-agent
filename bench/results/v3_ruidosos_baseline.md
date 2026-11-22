# Benchmark 2026-11-22 23:41

Conjunto: 16 casos sintéticos de `data/cases_ruidosos.jsonl`, gabarito em `data/ground_truth_ruidosos.json`.

| Abordagem | Acertos | F1 macro | Falso alarme em legítimos | Golpes vistos como sem fraude | Clientes acusados indevidamente | recall cobranca_extra | recall codigo_entrega | recall falso_atendente | recall link_malicioso | recall contestacao_suspeita | recall sem_fraude |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Só regras (baseline) | 12/16 (75.0%) | 0.665 | 0/5 | 2/11 | 0 | 0.75 | 0.67 | 0.00 | 1.00 | 1.00 | 1.00 |

## Casos com mais de um golpe

| Abordagem | Golpes encontrados | Casos com todos os golpes |
|---|---|---|
| Só regras (baseline) | 4/6 | 1/3 |
