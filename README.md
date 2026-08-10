# VOE LAB — Protótipos Públicos

Laboratório aberto com demonstrações independentes e dados totalmente fictícios para explorar experiências de micromobilidade urbana.

![Status](https://img.shields.io/badge/status-protótipos-ff786a?style=for-the-badge)
![Data](https://img.shields.io/badge/dados-100%25_fictícios-111827?style=for-the-badge)
![Security](https://img.shields.io/badge/sem_credenciais-público_seguro-22c55e?style=for-the-badge)

## Demonstrações

### Painel de frota

Abra `dashboard/index.html` no navegador para visualizar um painel estático com veículos fictícios, níveis simulados de bateria e indicadores operacionais.

### Simulador de telemetria

Execute:

```bash
node telemetry/simulator.js
```

O programa gera eventos locais de localização aproximada, bateria, estado e horário. Ele não se conecta a dispositivos, servidores, APIs ou veículos reais.

### Especificação de API

O arquivo `api/openapi.yaml` descreve uma API fictícia e somente de leitura para listar veículos demonstrativos.

## Princípios de segurança

- nenhum dado pessoal;
- nenhuma credencial;
- nenhum endpoint real;
- nenhuma conexão com veículos;
- nenhuma lógica de desbloqueio;
- nenhum código proprietário;
- identificadores e coordenadas fictícios.

## Aviso

Este repositório é uma demonstração técnica independente. Não representa um ambiente de produção nem permite operar veículos reais.

## Autor

**Davi Menezes** — VOE LAB  
Mobilidade urbana • Software • IoT • Produto
