# Política de Segurança — Sandbox Público

## Escopo

Este repositório contém somente contratos, protótipos e dados sintéticos. Não deve hospedar empresas, marcas privadas, segredos, credenciais, endpoints de produção, identificadores reais de ativos ou mecanismos capazes de controlar hardware.

## Pode ser publicado

- documentação de arquitetura;
- OpenAPI de sandbox;
- schemas sintéticos;
- simuladores locais sem acesso a hardware;
- dados fictícios;
- testes reproduzíveis;
- algoritmos genéricos.

## Não deve ser publicado

- nomes de empresas ou marcas privadas;
- chaves privadas;
- tokens;
- senhas;
- cookies de sessão;
- `.env` reais;
- credenciais de banco;
- certificados privados;
- números de série, IMEI, IMSI, MAC ou UUID reais;
- coordenadas reais de pessoas ou ativos;
- endpoints internos;
- dumps contendo dados reais;
- comandos de atuação física;
- procedimentos de desbloqueio, bypass ou provisionamento real.

## Modelo de confiança

Nenhuma entrada é confiável por padrão. Implementações devem validar tipo, tamanho, faixa numérica, enumeração, identificadores, timestamps, profundidade de objeto e propriedades inesperadas.

## Segredos

Segredos devem permanecer fora do Git e ser injetados por mecanismos adequados do ambiente. Os exemplos deste repositório não necessitam de segredos.

## Logs

Logs demonstrativos podem conter apenas identificadores sintéticos e metadados locais. Nunca registrar tokens, senhas, dados pessoais ou identificadores reais.

## Classificação

Todo dado público deste sandbox deve ser classificável como:

```text
synthetic-public-demo
```

Se não puder ser classificado assim, não deve ser publicado.
