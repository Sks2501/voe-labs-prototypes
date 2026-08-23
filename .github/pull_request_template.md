## Mudança de engenharia
Descreva o problema técnico, o contrato afetado e a estratégia de implementação.

## Classe do artefato
- [ ] Protocolo / RFC sintético
- [ ] OpenAPI / contrato HTTP
- [ ] Evento sintético
- [ ] Simulador determinístico
- [ ] Arquitetura / segurança
- [ ] Teste de conformidade / regressão
- [ ] Documentação

## Contrato e compatibilidade
- Versão do contrato:
- Comportamento anterior:
- Comportamento novo:
- Compatibilidade retroativa:
- Migração/depreciação:

## Análise de protocolo/parser
Quando aplicável, documente:

- limites de campos;
- endianness;
- versionamento;
- rejeição de entrada truncada;
- comportamento para tipos desconhecidos;
- integridade;
- limites de alocação/recursos.

## Falhas e resiliência
- Modos de falha esperados:
- Duplicação/reordenação:
- Timeout/cancelamento:
- Retry/idempotência:
- Backpressure:
- Estado degradado:

## Fronteira pública
- [ ] Dados exclusivamente sintéticos
- [ ] Sem empresas ou marcas privadas
- [ ] Sem dados reais de pessoas/clientes
- [ ] Sem identificadores reais de dispositivos
- [ ] Sem credenciais ou endpoints de produção
- [ ] Sem caminho de atuação física
- [ ] Sem procedimento de bypass/desbloqueio
- [ ] Sem código proprietário de terceiros

## Verificação
- [ ] Caso válido
- [ ] Valores de fronteira
- [ ] Entrada malformada
- [ ] Tipo/versão desconhecida
- [ ] Truncamento
- [ ] Duplicação/reordenação quando aplicável
- [ ] Regressão determinística

## Observabilidade
Descreva sinais, métricas, logs e campos de correlação necessários para diagnosticar comportamento sem expor informação sensível.

## Rollback
Descreva como reverter a mudança sem deixar contratos ambíguos.

## Gate
Não aprovar enquanto contrato, limites, falhas, compatibilidade, testes, segurança pública e rollback não estiverem explícitos.
