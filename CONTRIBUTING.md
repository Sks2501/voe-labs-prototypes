# Padrão de Contribuição — Engenharia de Sistemas

Este repositório é um sandbox público e genérico. Toda contribuição deve preservar a separação entre pesquisa reproduzível e sistemas reais.

## Escopo aceito

- especificações de protocolo sintético;
- contratos OpenAPI;
- eventos e telemetria fictícia;
- simuladores determinísticos;
- documentação de arquitetura;
- testes de conformidade;
- parsers e codecs usando frames artificiais;
- documentação de observabilidade e falhas.

## Não aceito

- nomes de empresas ou marcas privadas;
- credenciais;
- dados reais de clientes;
- topologia privada;
- identificadores reais de dispositivos;
- endpoints de produção;
- comandos de atuação física;
- procedimentos de bypass ou desbloqueio;
- código proprietário de terceiros.

## Workflow contract-first

Mudanças externas devem documentar:

1. versão do contrato;
2. invariantes;
3. limites de campos;
4. compatibilidade;
5. semântica de falha;
6. migração;
7. rollback;
8. testes de conformidade.

## Protocolos

Protocolos devem possuir tamanhos limitados, parsing determinístico, endianness explícita, versão, rejeição de entrada truncada, validação de integridade e comportamento definido para tipos desconhecidos.

## APIs

Contratos HTTP devem definir erros estáveis, correlação, paginação limitada, validação e compatibilidade. URLs públicas de exemplo devem permanecer não roteáveis.

## Testes

Cobrir quando aplicável:

- caminho válido;
- valores de fronteira;
- truncamento;
- tipo ou versão desconhecida;
- duplicação;
- reordenação;
- timeout;
- regressão determinística.

## Gate de revisão

Uma mudança não está pronta enquanto contrato, limites, compatibilidade, falhas, testes, segurança e rollback não estiverem explícitos.
