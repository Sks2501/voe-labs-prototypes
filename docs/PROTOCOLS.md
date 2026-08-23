# Protocolos Públicos — Systems Lab

## Escopo

Este documento descreve contratos sintéticos e genéricos para estudo de interoperabilidade, versionamento, parsing e observabilidade. Não representa protocolo proprietário ou operacional de empresa alguma.

## Identidade

Recursos demonstrativos usam:

```text
SYS-DEMO-01
SYS-DEMO-02
SYS-DEMO-03
```

Eventos usam:

```text
evt_demo_000001
```

## Família de eventos

```text
systems.lab.telemetry.demo.v1
```

Tipos:

```text
heartbeat.demo
metric.sample.demo
position.sample.demo
state.sample.demo
```

## Envelope

```json
{
  "schema": "systems.lab.telemetry.demo.v1",
  "eventId": "evt_demo_000001",
  "eventType": "metric.sample.demo",
  "sequence": 42,
  "resourceId": "SYS-DEMO-01",
  "recordedAt": "2026-08-23T21:00:00Z",
  "source": "local-simulator",
  "payload": {
    "metricPercent": 84,
    "status": "ready-demo"
  }
}
```

## Semântica de sequência

`sequence` serve para ordenação diagnóstica, detecção de lacunas e duplicação. Não é credencial, nonce criptográfico ou mecanismo de autenticação.

Consumidores devem tolerar:

- duplicação;
- atraso;
- eventos fora de ordem;
- lacunas explícitas;
- replay de fixtures.

## Compatibilidade

1. mudanças aditivas opcionais podem permanecer na mesma versão maior;
2. alteração de significado exige nova versão maior;
3. campos existentes não podem mudar unidade silenciosamente;
4. tipos obrigatórios desconhecidos devem falhar de forma fechada;
5. parsers não devem adivinhar layouts incompatíveis.

## Parsing

Antes de interpretar uma entrada:

1. validar tamanho mínimo;
2. validar tamanho máximo;
3. validar versão;
4. validar tipo;
5. validar comprimentos declarados;
6. validar integridade quando existir;
7. somente então interpretar payload.

## Estado sintético

```text
ready-demo
busy-demo
maintenance-demo
offline-demo
```

Estados são demonstrativos e não correspondem a ativos reais.

## HTTP

A superfície pública é somente leitura:

```text
GET /v1/status
GET /v1/resources
GET /v1/resources/{resourceId}
GET /v1/telemetry/events
```

## Erros

Códigos estáveis:

```text
INVALID_ARGUMENT
NOT_FOUND
RATE_LIMITED
INTERNAL_DEMO_ERROR
```

## Segurança

Nenhum contrato deste documento autoriza atuação física, controle remoto, bypass, provisionamento real ou acesso a infraestrutura privada.
