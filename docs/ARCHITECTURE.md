# Arquitetura — Sandbox Público de Sistemas

## Objetivo

Definir uma arquitetura pública, reproduzível e independente de qualquer empresa, marca, infraestrutura privada ou dispositivo real.

## Fronteiras

```text
┌───────────────────────────────┐
│       CONTRATO HTTP           │
│ validação · erros · paginação │
└──────────────┬────────────────┘
               ▼
┌───────────────────────────────┐
│       MODELO DE DOMÍNIO       │
│ recursos e estados sintéticos │
└──────────────┬────────────────┘
               ▼
┌───────────────────────────────┐
│       EVENTOS SINTÉTICOS      │
│ identidade · sequência · tempo│
└──────────────┬────────────────┘
               ▼
┌───────────────────────────────┐
│       PROTOCOLOS / PARSING    │
│ bounds · versão · integridade │
└──────────────┬────────────────┘
               ▼
┌───────────────────────────────┐
│       FERRAMENTAS LOCAIS      │
│ simuladores · fixtures · testes│
└───────────────────────────────┘
```

## Invariantes

1. toda entrada possui limite conhecido;
2. versões incompatíveis falham de forma fechada;
3. contratos externos não mudam silenciosamente;
4. eventos possuem identidade e sequência independentes;
5. duplicação não deve gerar efeitos colaterais duplicados;
6. erros possuem representação estável;
7. exemplos públicos usam dados sintéticos;
8. nenhum componente público exige segredo;
9. dependências externas devem possuir timeout;
10. retries devem ser limitados e seguros para a operação.

## Classes de falha

### Entrada inválida

Rejeitar antes da interpretação de domínio.

### Versão desconhecida

Rejeitar quando a compatibilidade não puder ser provada.

### Integridade inválida

Descartar o frame/evento e produzir diagnóstico sem reproduzir conteúdo sensível.

### Dependência indisponível

Aplicar timeout, retry limitado, backoff e circuit breaker quando semanticamente seguro.

### Duplicação

Consumidores devem trabalhar com idempotência ou deduplicação explícita.

### Sobrecarga

Filas devem possuir capacidade limitada e política de backpressure.

## Observabilidade

Diagnósticos devem priorizar:

- `requestId`;
- `correlationId`;
- versão de contrato;
- classe de erro;
- latência;
- tamanho de fila;
- quantidade de retries;
- estado de circuit breaker;
- contadores agregados.

Não registrar segredos, dados pessoais ou identificadores reais.

## Não objetivos

Este sandbox não implementa operações físicas, provisionamento real, desbloqueio, bypass, firmware proprietário, credenciais ou integração com sistemas de produção.
