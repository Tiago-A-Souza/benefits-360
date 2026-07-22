# Fixtures de paridade — rascunhos nativos da aplicação (ETAPA 2.2.6)

Cada caso (`demo_12`, `demo_41`) contém:

| Arquivo | Conteúdo |
|---------|----------|
| `rascunho.json` | Entrada canônica da aplicação |
| `expected_estudo_input.json` | Saída integral do compilador → motor |
| `expected_policy.json` | `EffectivePolicy` esperada |
| `expected_motor_result.json` | `MotorResult` integral após `calcular()` |

Os testes comparam **integralmente** esses artefatos. Não converter fixtures do motor (`tests/fixtures/renovacao_*`).

Os seeds `rascunho_demo_*_vidas()` devem produzir o mesmo JSON de `rascunho.json` (teste anti-deriva).
