# RFC-0001 — Frame Binário Sintético

**Status:** experimental  
**Escopo:** laboratório público e genérico  
**Compatibilidade:** nenhuma relação com protocolos proprietários ou operacionais reais

## 1. Objetivo

Definir um frame artificial para demonstrar parsing determinístico, limites de memória, versionamento e integridade.

## 2. Layout

```text
Offset  Tamanho  Campo
0       2        Magic
2       1        Version
3       1        Type
4       2        PayloadLength (big-endian)
6       N        Payload
6+N     4        CRC32 IEEE
```

## 3. Limites

```text
payload máximo: 256 bytes
header fixo: 6 bytes
CRC: 4 bytes
frame máximo: 266 bytes
```

Um parser deve rejeitar `PayloadLength > 256` antes de copiar qualquer payload.

## 4. Magic

Valor sintético de exemplo:

```text
A5 5A
```

O magic serve apenas para sincronização de framing e não constitui segurança.

## 5. Version

Versão inicial:

```text
0x01
```

Versões não reconhecidas devem ser rejeitadas, exceto quando um contrato futuro definir compatibilidade explícita.

## 6. Type

`Type` identifica famílias exclusivamente sintéticas. Este RFC não define comandos de atuação física.

## 7. PayloadLength

Inteiro unsigned de 16 bits em big-endian. A implementação deve validar:

```text
PayloadLength <= 256
frame_length == 6 + PayloadLength + 4
```

## 8. CRC32

CRC32 IEEE, polinômio refletido `0xEDB88320`, calculado sobre header + payload e excluindo o próprio campo CRC.

CRC detecta corrupção acidental; não fornece autenticidade criptográfica.

## 9. Ordem de validação

```text
1. ponteiro/entrada válida
2. tamanho mínimo
3. magic
4. versão
5. payload length
6. tamanho total
7. CRC
8. cópia/interpretação
```

## 10. Taxonomia de erro

```text
argumento_nulo
frame_curto
magic_invalido
versao_invalida
payload_excede_limite
comprimento_inconsistente
crc_invalido
```

## 11. Propriedades desejadas

- parsing sem alocação dinâmica;
- memória máxima conhecida;
- nenhuma leitura fora dos limites;
- comportamento determinístico;
- falha fechada;
- testes negativos reproduzíveis.

## 12. Segurança

Este RFC é propositalmente artificial. Não documenta protocolo de empresa, dispositivo comercial, sistema de transporte, firmware ou infraestrutura operacional.
