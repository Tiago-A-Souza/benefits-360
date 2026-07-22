# Fixtures de paridade — rascunhos nativos da aplicação (ETAPA 2.2)

Cada caso declara explicitamente:

- `rascunho.json` — entrada da aplicação
- `expected_policy.json` — EffectivePolicy esperada após compilação
- `expected_motor.json` — resumo do MotorResult (não fixture do motor)

**Não** converter fixtures do motor (`tests/fixtures/renovacao_*`) para rascunho.
