# Triagem de denúncias de fraude

Modelo: `gemini-3.5-flash-lite` · 17 casos · 10.19 s · 3 chamadas ao LLM

## Resumo

- Ação recomendada: **9**
- Revisão humana: **3**
- Encerrados sem fraude: **5**

| Categoria | Casos |
|---|---:|
| Sem fraude | 7 |
| Cobrança extra na entrega | 4 |
| Código de entrega obtido antes da entrega | 2 |
| Link malicioso | 2 |
| Contestação suspeita | 1 |
| Falso atendente | 1 |

## Fila de trabalho

| Caso | Prioridade | Status | Categoria | Evidência | Aprovação necessária |
|---|---|---|---|---|---|
| H003 | alta | revisão humana | Cobrança extra na entrega | Me pediram 8 reais de pix na entrega. | alertar_cliente, estornar_cobranca_indevida, suspender_entregador_cautelarmente |
| H006 | media | revisão humana | Sem fraude | — | — |
| H010 | media | revisão humana | Sem fraude | Dei uma gorjeta de 5 reais no cartão por vontade própria. Tudo certo. | — |
| H004 | alta | ação recomendada | Código de entrega obtido antes da entrega | me manda aqueles 4 números que aparecem no app pra eu finalizar | reembolsar_pedido, investigar_entregador |
| H007 | alta | ação recomendada | Falso atendente | Me ligaram do 'setor de fraudes' do app dizendo que minha conta foi invadida e que eu prec | denunciar_contato_falso |
| H008 | alta | ação recomendada | Link malicioso | Chegou mensagem 'seu cashback expira hoje' com o link tinyurl.com/cashback-app pedindo meu | solicitar_derrubada_do_dominio |
| H009 | alta | ação recomendada | Código de entrega obtido antes da entrega | Teu pedido tá preso no sistema, só libera com a senha de entrega | reembolsar_pedido, investigar_entregador |
| H011 | alta | ação recomendada | Cobrança extra na entrega | Paguei pelo app e na hora o motoboy falou que faltava a taxa de chuva. Paguei R$ 12,00 no  | estornar_cobranca_indevida, suspender_entregador_cautelarmente |
| H014 | alta | ação recomendada | Cobrança extra na entrega | mano a taxa d entrega nao caiu no app, vo passa no debito blz | estornar_cobranca_indevida, suspender_entregador_cautelarmente |
| H015 | alta | ação recomendada | Cobrança extra na entrega | A maquininha deu erro na primeira, vou passar de novo | estornar_cobranca_indevida, suspender_entregador_cautelarmente |
| H017 | alta | ação recomendada | Link malicioso | Recebi https://deliveryapp.example.promo-natal.top/cupom com cupom de Natal e o site pediu | solicitar_derrubada_do_dominio |
| H001 | media | ação recomendada | Contestação suspeita | valeu! | revisar_historico_do_cliente |

## Por que foram para revisão

- **H003**: texto do caso tenta dar ordens à IA (injeção de prompt, apontada pelo modelo)
- **H006**: modelo diz sem fraude, mas há sinal forte: codigo_validado_longe
- **H010**: modelo diz sem fraude, mas há sinal forte: valor_acima_do_pedido
