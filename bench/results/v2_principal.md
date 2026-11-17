# Benchmark 2026-11-17 20:34

Conjunto: 48 casos sintéticos de `data/cases.jsonl`, gabarito em `data/ground_truth.json`.

| Abordagem | Acertos | F1 macro | Falso alarme em legítimos | Golpes vistos como sem fraude | Clientes acusados indevidamente | recall cobranca_extra | recall codigo_entrega | recall falso_atendente | recall link_malicioso | recall contestacao_suspeita | recall sem_fraude |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Só regras (baseline) | 35/48 (72.9%) | 0.709 | 0/8 | 13/40 | 0 | 0.88 | 1.00 | 0.12 | 1.00 | 0.38 | 1.00 |
| gemini-3.1-flash-lite + política (rodada 1) | 48/48 (100.0%) | 1.000 | 0/8 | 0/40 | 0 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |

## Rodada 1: gemini-3.1-flash-lite

- Tempo: 36.59 s, 6 chamadas, 15775 tokens de entrada e 8157 de saída
- Injeções enviadas para revisão: 3/3 (regra: 3/3, modelo: 3/3, falsos positivos: 0)
- Casos em revisão humana: 4
- Erros do modelo retidos na revisão: 0
- Erros do modelo que passaram direto: 0 
- Citações literais: 38/38
- Avisos: 0
