# Sandbox Público de Engenharia de Sistemas

![OpenAPI](https://img.shields.io/badge/OpenAPI-3.0.3-111827?style=flat-square&logo=openapiinitiative)
![Protocols](https://img.shields.io/badge/protocolos-versionados-111827?style=flat-square)
![Architecture](https://img.shields.io/badge/arquitetura-failure_oriented-111827?style=flat-square)
![Data](https://img.shields.io/badge/dados-sintéticos-111827?style=flat-square)
![Security](https://img.shields.io/badge/segurança-sem_segredos-111827?style=flat-square)

Laboratório público e genérico para estudo de contratos de API, protocolos, telemetria sintética, compatibilidade, parsing determinístico e comportamento sob falhas.

Este repositório não representa empresa, marca, frota, infraestrutura privada ou sistema de produção.

## Modelo lógico

```text
CONTRATO HTTP
    ↓
MODELO DE DADOS SINTÉTICO
    ↓
ENVELOPES DE EVENTOS
    ↓
PROTOCOLOS E PARSING
    ↓
SIMULADORES LOCAIS
```

## Conteúdo

```text
README.md
SECURITY.md
CONTRIBUTING.md
api/openapi.yaml
dashboard/index.html
docs/ARCHITECTURE.md
docs/PROTOCOLS.md
docs/RFC-0001-SYNTHETIC-FRAME.md
telemetry/simulator.js
```

## Contratos HTTP

A especificação `api/openapi.yaml` define uma API exclusivamente demonstrativa e somente leitura:

```text
GET /v1/status
GET /v1/resources
GET /v1/resources/{resourceId}
GET /v1/telemetry/events
```

Ela inclui paginação limitada, erros estáveis, `requestId`, validação de parâmetros, schemas e semântica de rate limit.

## Eventos sintéticos

Família atual:

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

Os identificadores usam exclusivamente o prefixo genérico `SYS-DEMO`.

## Regras

- dados exclusivamente sintéticos;
- nenhuma empresa ou marca necessária para o funcionamento;
- nenhum segredo;
- nenhum endpoint de produção;
- nenhum identificador de hardware real;
- nenhuma informação pessoal;
- nenhuma operação de controle físico;
- nenhum procedimento de bypass;
- nenhum código proprietário de terceiros.

## Filosofia

```text
contratos explícitos       > acoplamento implícito
parsing limitado           > entrada sem limite
fail closed                > adivinhação permissiva
idempotência               > efeitos duplicados
falha observável           > estado invisível
dados sintéticos           > exposição operacional
```

## Execução local

```bash
node telemetry/simulator.js
```

O simulador não acessa rede, Bluetooth, serial, arquivos privados ou dispositivos físicos.
