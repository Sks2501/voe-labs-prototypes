# VOE LAB — Protótipos Públicos

Laboratório aberto com demonstrações independentes e dados totalmente fictícios para explorar experiências de micromobilidade urbana.

![Status](https://img.shields.io/badge/status-protótipos-ff786a?style=for-the-badge)
![Data](https://img.shields.io/badge/dados-100%25_fictícios-111827?style=for-the-badge)
![Security](https://img.shields.io/badge/sem_credenciais-público_seguro-22c55e?style=for-the-badge)
![API](https://img.shields.io/badge/OpenAPI-3.0.3-6BA539?style=for-the-badge&logo=openapiinitiative&logoColor=white)
![Protocol](https://img.shields.io/badge/protocolo-versionado-2563EB?style=for-the-badge)

## Visão geral

O repositório reúne protótipos públicos e seguros para demonstrar arquitetura de software aplicada à micromobilidade sem conectar-se a veículos, usuários, servidores de produção ou infraestrutura operacional.

A arquitetura demonstrativa está separada em três superfícies:

```text
Dashboard estático
      │
      ▼
Public Sandbox API Contract
      │
      ▼
Telemetry Demo Event Contract
      │
      ▼
Simulador local sem acesso a hardware
```

## Demonstrações

### Painel de frota

Abra `dashboard/index.html` no navegador para visualizar um painel estático com veículos fictícios, níveis simulados de bateria e indicadores operacionais.

### Simulador de telemetria

Execute:

```bash
node telemetry/simulator.js
```

O programa gera eventos locais de localização aproximada, bateria, estado e horário. Ele não se conecta a dispositivos, servidores, APIs, Bluetooth, UART, serial ou veículos reais.

### Especificação pública da API

O arquivo `api/openapi.yaml` contém a especificação OpenAPI 3.0.3 do sandbox demonstrativo.

A versão 2 inclui contratos somente leitura para:

- `GET /v1/status`
- `GET /v1/vehicles`
- `GET /v1/vehicles/{vehicleId}`
- `GET /v1/telemetry/events`

A especificação define paginação, envelopes padronizados, erros, `requestId`, rate limiting conceitual, schemas de veículo e contratos de telemetria.

### Protocolos públicos

A documentação técnica completa está em [`docs/PROTOCOLS.md`](docs/PROTOCOLS.md).

Ela descreve:

- arquitetura de contratos públicos;
- versionamento;
- modelo de eventos;
- identidade de recursos;
- estados demonstrativos;
- ordenação de telemetria;
- compatibilidade;
- observabilidade;
- threat model;
- limites explícitos de segurança.

## Contrato de telemetria

Schema atual:

```text
voe.lab.telemetry.demo.v1
```

Eventos públicos modelados:

```text
heartbeat.demo
battery.sample.demo
position.sample.demo
state.sample.demo
```

Exemplo:

```json
{
  "schema": "voe.lab.telemetry.demo.v1",
  "eventId": "evt_demo_000001",
  "eventType": "battery.sample.demo",
  "sequence": 42,
  "vehicleId": "VOE-DEMO-01",
  "recordedAt": "2026-08-23T06:00:00Z",
  "source": "local-simulator",
  "payload": {
    "batteryPercent": 84,
    "status": "available-demo",
    "zone": "Estação Coral",
    "coordinates": {
      "latitude": -22.9,
      "longitude": -43.18,
      "precision": "synthetic"
    }
  }
}
```

## Regras de segurança

- somente informações fictícias;
- nenhuma chave, senha ou token real;
- arquivos `.env` nunca são enviados;
- nenhum endpoint de produção;
- nenhuma informação pessoal de clientes;
- nenhuma conexão com veículos;
- nenhuma lógica de desbloqueio;
- nenhum comando operacional de hardware;
- nenhum código proprietário obtido de terceiros;
- identificadores, zonas e coordenadas fictícios.

## Estrutura

```text
voe-labs-prototypes/
├── README.md
├── api/
│   └── openapi.yaml
├── dashboard/
│   └── index.html
├── docs/
│   └── PROTOCOLS.md
└── telemetry/
    └── simulator.js
```

## Filosofia de arquitetura

```text
Publicável
    +
Reproduzível
    +
Versionado
    +
Sem segredos
    +
Sem atuação física
    =
Sandbox técnico seguro
```

## Aviso

Este repositório é uma demonstração técnica independente. Não representa um ambiente de produção e não permite operar veículos reais. Protocolos públicos neste projeto são contratos de sandbox destinados a estudo de arquitetura, testes e documentação.

## Autor

**Davi Menezes** — VOE LAB  
Mobilidade urbana • Software • IoT • Produto
