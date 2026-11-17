# Benchmark 2026-11-17 20:31

Conjunto: 17 casos sintéticos de `data/cases_dificeis.jsonl`, gabarito em `data/ground_truth_dificeis.json`.

| Abordagem | Acertos | F1 macro | Falso alarme em legítimos | Golpes vistos como sem fraude | Clientes acusados indevidamente | recall cobranca_extra | recall codigo_entrega | recall falso_atendente | recall link_malicioso | recall contestacao_suspeita | recall sem_fraude |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Só regras (baseline) | 11/17 (64.7%) | 0.499 | 2/7 | 4/10 | 0 | 0.50 | 1.00 | 0.00 | 1.00 | 0.00 | 0.71 |
| gemini-3.5-flash-lite + política (rodada 1) | 17/17 (100.0%) | 1.000 | 0/7 | 0/10 | 0 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| gemini-3.1-flash-lite + política (rodada 2) | 17/17 (100.0%) | 1.000 | 0/7 | 0/10 | 0 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |

## Rodada 1: gemini-3.5-flash-lite

- Tempo: 9.05 s, 3 chamadas, 6012 tokens de entrada e 2590 de saída
- Injeções enviadas para revisão: 0/1 (regra: ?, modelo: ?, falsos positivos: ?)
- Casos em revisão humana: 2
- Erros do modelo retidos na revisão: 0
- Erros do modelo que passaram direto: 0 
- Citações literais: 13/13
- Avisos: 0

## Rodada 2: gemini-3.1-flash-lite

- Tempo: 8.01 s, 3 chamadas, 6012 tokens de entrada e 2494 de saída
- Injeções enviadas para revisão: 0/1 (regra: ?, modelo: ?, falsos positivos: ?)
- Casos em revisão humana: 2
- Erros do modelo retidos na revisão: 0
- Erros do modelo que passaram direto: 0 
- Citações literais: 10/10
- Avisos: 0
