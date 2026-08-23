# VOE LAB — Protocolos Públicos de Demonstração

## 1. Objetivo

Este documento define contratos públicos, versionados e estritamente demonstrativos para o repositório VOE LAB. Todos os fluxos aqui descritos operam somente com dados sintéticos e não devem ser interpretados como interfaces de produção, firmware proprietário, mecanismos de desbloqueio, provisionamento, manutenção remota ou controle físico de veículos.

## 2. Princípios arquiteturais

Os protocolos seguem os seguintes princípios:

- **Read-only by design:** nenhuma interface pública de demonstração executa comandos físicos.
- **Synthetic data only:** IDs, coordenadas, estados, eventos e exemplos são fictícios.
- **Explicit versioning:** contratos carregam versão semântica ou identificador de schema.
- **Deterministic validation:** payloads possuem tipos, limites e enums conhecidos.
- **Idempotent reads:** consultas GET podem ser repetidas sem produzir efeitos colaterais.
- **Traceability:** respostas e eventos usam IDs de correlação demonstrativos.
- **Fail closed:** entradas fora do contrato devem ser rejeitadas.
- **No implicit trust:** nenhum identificador de demonstração representa autenticação ou autorização real.

## 3. Camadas públicas

```text
┌─────────────────────────────────────────────────────┐
│                 Consumidor demonstrativo            │
│ Dashboard • CLI • testes • documentação • exemplos │
└───────────────────────┬─────────────────────────────┘
                        │ HTTPS/JSON conceitual
┌───────────────────────▼─────────────────────────────┐
│              Public Sandbox Contract v2             │
│ /v1/status • /v1/vehicles • /v1/telemetry/events   │
└───────────────────────┬─────────────────────────────┘
                        │ eventos sintéticos
┌───────────────────────▼─────────────────────────────┐
│            Telemetry Demo Event Contract v1         │
│ heartbeat • battery • position • state             │
└───────────────────────┬─────────────────────────────┘
                        │ origem local simulada
┌───────────────────────▼─────────────────────────────┐
│               Local Telemetry Simulator             │
│ Sem BLE • Sem UART • Sem rede • Sem hardware real  │
└─────────────────────────────────────────────────────┘
```

## 4. Protocolo HTTP público

### 4.1 Representação

- Media type: `application/json`
- Encoding: UTF-8
- Datas: RFC 3339 / ISO 8601 em UTC
- IDs públicos: strings opacas
- Paginação: `page` e `pageSize`
- Operações públicas: somente `GET`

### 4.2 Envelope de resposta

Toda resposta bem-sucedida segue a forma:

```json
{
  "data": {},
  "meta": {
    "requestId": "req_demo_01JABCDEF1234567890",
    "generatedAt": "2026-08-23T06:00:00Z",
    "dataClassification": "synthetic-public-demo"
  }
}
```

Coleções adicionam metadados de paginação:

```json
{
  "data": [],
  "meta": {
    "requestId": "req_demo_01JABCDEF1234567890",
    "generatedAt": "2026-08-23T06:00:00Z",
    "dataClassification": "synthetic-public-demo",
    "page": 1,
    "pageSize": 25,
    "totalItems": 3,
    "totalPages": 1
  }
}
```

### 4.3 Envelope de erro

```json
{
  "error": {
    "code": "INVALID_ARGUMENT",
    "message": "Um ou mais parâmetros são inválidos.",
    "requestId": "req_demo_01JABCDEF1234567890"
  }
}
```

Códigos públicos definidos:

| Código | Significado |
|---|---|
| `INVALID_ARGUMENT` | parâmetro fora do contrato |
| `NOT_FOUND` | recurso sintético inexistente |
| `RATE_LIMITED` | limite lógico do sandbox excedido |
| `INTERNAL_DEMO_ERROR` | erro interno exclusivamente demonstrativo |

## 5. Identidade de recursos

Veículos fictícios usam o padrão:

```text
VOE-DEMO-[0-9]{2}
```

Exemplos válidos:

```text
VOE-DEMO-01
VOE-DEMO-02
VOE-DEMO-03
```

Esses identificadores nunca devem corresponder a número de série, IMEI, MAC address, VIN, UUID de dispositivo ou qualquer identidade operacional real.

## 6. Estados demonstrativos

Estados públicos aceitos:

```text
available-demo
charging-demo
maintenance-demo
offline-demo
```

São estados visuais e semânticos. Nenhum estado aciona relé, trava, controlador, bateria, BMS, modem, ECU, display ou outro componente físico.

## 7. Protocolo de telemetria sintética

### 7.1 Schema

Cada evento usa:

```text
voe.lab.telemetry.demo.v1
```

### 7.2 Tipos de evento

```text
heartbeat.demo
battery.sample.demo
position.sample.demo
state.sample.demo
```

### 7.3 Estrutura canônica

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

## 8. Ordenação e sequência

O campo `sequence` é monotônico dentro de uma execução local do simulador. Ele não representa contador persistente de hardware.

Consumidores demonstrativos devem:

1. aceitar a sequência como número inteiro não negativo;
2. não inferir perda operacional de pacotes reais;
3. tolerar reinício da sequência após reinício do simulador;
4. usar `recordedAt` apenas como horário de geração sintética.

## 9. Coordenadas

Todas as coordenadas são classificadas como:

```text
precision = synthetic
```

Elas existem exclusivamente para visualização e testes. Não representam localização de pessoa, veículo, base operacional, depósito ou ativo real.

## 10. Compatibilidade

A política de compatibilidade é:

- alterações aditivas e opcionais podem manter a mesma versão de schema;
- remoção ou mudança semântica de campo exige nova versão;
- novos valores obrigatórios em enums exigem revisão de compatibilidade;
- consumidores devem ignorar campos opcionais desconhecidos apenas quando o schema permitir extensibilidade;
- contratos documentados em OpenAPI são a fonte normativa para HTTP.

## 11. Rate limiting demonstrativo

A especificação descreve `429 RATE_LIMITED` apenas para modelagem de cliente. Uma implementação futura de sandbox pode aplicar limites por origem sem armazenar identidade pessoal.

Clientes devem respeitar o header:

```text
Retry-After: <segundos>
```

E usar retry limitado com backoff exponencial e jitter em ambientes de teste.

## 12. Segurança

É proibido incluir neste repositório público:

- chaves de API;
- tokens JWT reais;
- cookies de sessão;
- certificados privados;
- senhas;
- endpoints de produção;
- IPs internos;
- credenciais de banco;
- números de série reais;
- comandos CAN, UART, BLE, MQTT ou similares capazes de atuar em hardware;
- procedimentos de bypass, desbloqueio ou provisionamento de dispositivos reais;
- dados pessoais de usuários, clientes ou operadores.

## 13. Threat model do sandbox

Mesmo sendo demonstrativo, os consumidores devem considerar:

- payload malformado;
- campos inesperados;
- strings excessivamente grandes;
- enum desconhecido;
- timestamps inválidos;
- repetição de evento;
- eventos fora de ordem;
- resposta incompleta;
- indisponibilidade temporária;
- limite de requisições.

O comportamento recomendado é validar entrada, limitar tamanho, rejeitar estruturas inválidas e registrar falhas sem armazenar segredos.

## 14. Observabilidade demonstrativa

Campos recomendados em logs locais:

```text
requestId
eventId
schema
eventType
vehicleId
sequence
recordedAt
validationResult
```

Não registrar credenciais, tokens, cookies, dados pessoais ou informações de hardware real.

## 15. Fonte normativa

Para contratos HTTP, consulte `api/openapi.yaml`.

Para geração local de eventos, consulte `telemetry/simulator.js`.

Este documento descreve a arquitetura e as garantias de segurança que envolvem ambos.
