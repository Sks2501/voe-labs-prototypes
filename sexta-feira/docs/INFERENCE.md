# Inferência e preservação OpenAI GPT-2

O motor principal desta versão é o **OpenAI GPT-2 124M original**, em CPU float32.
Não há API comercial, serviços de inferência externos, Ollama ou modelos de outras
empresas. Nenhum peso foi treinado, refinado ou melhorado. A personalização em
português é contexto textual, e não transforma GPT-2 em um modelo de instruções.

## Procedência e execução

Os sete arquivos são baixados sem conversão do [host oficial usado pelo repositório
OpenAI](https://openaipublic.blob.core.windows.net/gpt-2/models/124M/hparams.json).
`weights.py` valida tamanho, MD5 publicado pelo blob e SHA-256 fixado no código
para 124M. Estes SHA-256 foram medidos por este projeto a partir do download HTTPS
em 10/11/2026; não são assinatura digital publicada pela OpenAI. O manifesto local
também é verificado integralmente antes da carga. A operação normal não faz downloads.

O leitor restrito de TensorBundle aceita somente os tensores float32 de uma única
partição no formato sem compressão observado nesse checkpoint. Ele interpreta
metadados e arrays, sem executar grafos TensorFlow, pickle ou código de modelos.
Os arquivos `.index`, `.meta` e `.data` originais permanecem intactos no disco.

`inference_torch.py` é uma transcrição independente das equações de
`openai-gpt2/src/model.py` em PyTorch. Mantém as matrizes originais sem transposição
de armazenamento, embeddings de entrada/saída compartilhados, GELU tanh, normas
com epsilon 1e-5, atenção causal e cache KV. Calcula logits de vocabulário apenas
na última posição. Não executa o runtime TensorFlow original. Não usa Transformers.

Há uma cópia original intocada dos seis componentes solicitados e da licença em
`openai-gpt2/upstream-original/`. `PROVENANCE.json` registra o commit
`9b63575ef42771a015060c964af2c3da4cf7c8ab` e SHA-256 por arquivo. A fonte é
[openai/gpt-2](https://github.com/openai/gpt-2/tree/9b63575ef42771a015060c964af2c3da4cf7c8ab).

## Alterações no código original

| Arquivo | Alteração e justificativa |
| --- | --- |
| `src/encoder.py` | Cache LRU configurável, padrão 4096 entradas, teto 65536, opção zero e limpeza explícita; limita crescimento. Trata sequência vazia e valida texto. Preserva codificação BPE, verificada contra original. |
| `src/model.py` | Valida dimensões e divisibilidade dos heads; verifica contexto total incluindo KV antes de acessar posições. Não altera pesos ou equações. |
| `src/sample.py` | Valida comprimento, temperatura finita, top-k, top-p e tamanho do lote. Impede divisão por zero, valores NaN e janelas inválidas. |
| `src/interactive_conditional_samples.py` | Valida lotes, restringe contexto, usa CPU com uma thread e trata EOF/Ctrl+C no prompt. Parte dessas adaptações já existia na ramificação e foi preservada. |
| `src/generate_unconditional_samples.py` | Padrão finito de uma amostra e 64 tokens; corrige contagem de amostras e valida lotes; CPU com uma thread. |
| `download_model.py` | Wrapper do downloader validado: apenas 124M/355M explícitos, timeout, origem HTTPS, limite de bytes, reserva de disco, hashes, temporários únicos e conclusão atômica. Não apaga arquivos preexistentes em falhas. |

Os exemplos TensorFlow legados não foram executados neste Windows/Python moderno;
suas alterações foram verificadas por leitura e compilação sintática. O adaptador
PyTorch e o checkpoint oficial foram executados de fato.

## Limites operacionais

Padrões: uma inferência ativa, duas aguardando, uma thread CPU, até 512 tokens de
entrada e 64 novos, deadline de 60 segundos incluindo espera. `SEXTA_CPU_THREADS`
aceita 1–2, `SEXTA_QUEUE_LIMIT` 1–8, `SEXTA_INFERENCE_TIMEOUT` 5–180 e
`SEXTA_MEMORY_RESERVE_MB` 512–8192 (padrão 1024). As faixas são limites de
configuração, não recomendação para aumentar recursos.

A carga verifica RAM livre para pesos e runtime e preserva a reserva. Cada token
reavalia a reserva. Não há limite rígido de memória do processo; um Windows Job
Object ou política equivalente poderá complementar essa proteção após medições
no servidor. O cancelamento é cooperativo entre tokens; uma operação nativa em
andamento não pode ser interrompida imediatamente. Três falhas operacionais
consecutivas ativam pausa de 60 segundos, sem ciclos de recarga paralelos.

A inicialização é preguiçosa e serializada. Trocar de 124M para 355M exige reiniciar
o processo; instâncias de ambos não coexistem. O 355M é apenas opção explícita,
não foi baixado, medido nem aprovado para o servidor. Quantização e GPU permanecem
desativadas porque ainda não foram validadas.

## Validação executada

`tests/test_inference.py` cobre fila cheia, cancelamento, encerramento, reserva de
RAM, carga concorrente única, fontes preservadas, rejeição de checkpoint inválido,
download excessivo, nova tentativa preservando parciais e detecção de alteração.

`tests/test_inference_model.py`, com `SEXTA_RUN_MODEL_TESTS=1`, carrega o checkpoint
real e compara tokenização UTF-8 contra original, logits contra uma implementação
NumPy independente, cache KV contra contexto completo, geração e validação de
parâmetros. **Não foi executada comparação numérica contra TensorFlow 1.x**.

Os resultados e tempos medidos estão em `benchmark-local.json`. Foram obtidos no
Windows 11/i5-4570 de desenvolvimento, e não no Dell/Windows Server acessado por
RDP. São evidência de funcionamento e referência local, não promessa de desempenho
ou memória no servidor. Não há conteúdo privado de conversas nesse relatório.

Arquivos `.part.<uuid>` de downloads interrompidos são preservados para diagnóstico;
novas tentativas usam outro nome e não os sobrescrevem. Revise espaço livre antes
de remover manualmente apenas parciais identificados como dispensáveis.
