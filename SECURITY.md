# Política de Segurança — VOE LAB Public Prototypes

## Escopo

Este repositório contém apenas protótipos, contratos e dados sintéticos. Ele não deve hospedar segredos, credenciais, endpoints de produção, identificadores reais de ativos ou mecanismos capazes de controlar hardware.

## O que pode ser publicado

- documentação de arquitetura;
- OpenAPI de sandbox;
- schemas de eventos sintéticos;
- simuladores locais sem acesso a rede ou hardware;
- interfaces estáticas;
- dados fictícios;
- testes e exemplos reproduzíveis.

## O que não deve ser publicado

- chaves privadas;
- tokens de acesso;
- senhas;
- cookies de sessão;
- `.env` reais;
- credenciais de banco de dados;
- certificados privados;
- números de série, IMEI, IMSI, MAC ou UUID reais de dispositivos;
- coordenadas reais de usuários ou ativos;
- endpoints internos ou de produção;
- dumps de memória ou banco com dados reais;
- comandos ou procedimentos destinados a desbloquear, reconfigurar, provisionar ou controlar dispositivos físicos reais.

## Modelo de confiança

Nenhuma entrada deve ser considerada confiável. Implementações derivadas dos contratos devem validar:

- tipo;
- tamanho;
- faixa numérica;
- enumeração;
- formato de identificador;
- timestamp;
- profundidade de objeto;
- propriedades inesperadas.

## Segredos

Segredos devem permanecer fora do Git e ser fornecidos exclusivamente por mecanismos apropriados do ambiente de execução. Este repositório público não possui necessidade legítima de segredos para suas demonstrações atuais.

## Dependências

Uma implementação futura deve:

1. fixar versões de dependências;
2. manter lockfile;
3. revisar atualizações de segurança;
4. evitar dependências desnecessárias;
5. executar análise estática e validação de configuração em CI.

## Logs

Logs demonstrativos podem conter somente identificadores sintéticos e metadados de execução local. Nunca registrar tokens, cookies, senhas, dados pessoais ou identificadores reais de hardware.

## Divulgação responsável

Caso seja identificado um problema de segurança relacionado exclusivamente ao conteúdo público deste repositório, abra uma issue descrevendo o impacto sem publicar segredos, dados pessoais ou material operacional sensível.

Caso a descoberta envolva credenciais reais ou dados que não deveriam estar públicos, não os reproduza em uma issue pública. Revogue ou remova o segredo na origem e trate o histórico do repositório conforme as práticas de resposta a incidentes do GitHub.

## Classificação

Todo dado incluído nas demonstrações deve ser classificável como:

```text
synthetic-public-demo
```

Se um dado não puder ser claramente classificado dessa forma, ele não deve ser adicionado ao repositório público.
