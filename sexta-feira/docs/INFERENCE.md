# Inferência local e preservação OpenAI GPT-2

## Backend atual: Gemma 3 4B IT

Depois da autorização posterior do proprietário para uma alternativa gratuita, o
backend instalado passou a `llama.cpp`. É outro modelo e outra arquitetura, da Google;
não é uma otimização dos pesos GPT-2. Os arquivos OpenAI abaixo continuam intactos.

`scripts/prepare_local_model.py` baixa e verifica dois artefatos fixados:

| Artefato | Origem fixada | SHA-256 |
| --- | --- | --- |
| `gemma-3-4b-it-Q4_K_M.gguf` (2.489.757.856 bytes) | [ggml-org, revisão d0976223747697cb51e056d85c532013931fe52e](https://huggingface.co/ggml-org/gemma-3-4b-it-GGUF/tree/d0976223747697cb51e056d85c532013931fe52e) | `882e8d2db44dc554fb0ea5077cb7e4bc49e7342a1f0da57901c0802ea21a0863` |
| CPU Windows x64 ZIP (25.058.018 bytes) | [llama.cpp b12282](https://github.com/ggml-org/llama.cpp/releases/tag/b12282) | `582a5da726b30e0b9e801b4ebd1b85cbe023ca266bdebf6a9d55426c85e57463` |

O hash do GGUF vem dos metadados LFS da revisão; o ZIP usa o digest do release.
O recibo local registra também os hashes de cada binário extraído. O serviço verifica
novamente os arquivos antes de carregar. A execução é offline, CPU apenas, sem
downloads automáticos, com um slot, duas threads, prioridade BelowNormal, contexto
2048, entrada 1536, saída 192 e fila externa de duas. A inicialização exige 5 GiB
livres; novas inferências reservam preventivamente pelo menos 2 GiB. São verificações
de admissão, não limites rígidos de memória do Windows.

`inference_llama.py` envia mensagens estruturadas ao template nativo, conta tokens
antes de gerar e remove pares antigos até caber. Mantém até quatro mensagens e três
memórias pertinentes. Um ID de corte exclui respostas GPT-2 antigas do contexto sem
apagar o histórico. A credencial nativa é separada da credencial da API. Somente
HTTP autenticado em `127.0.0.1:18765`, sem proxy ou redirecionamento, é aceito.
O stream é fechado em cancelamento; timeout de socket limita um prefill travado.
Comandos explícitos continuam no módulo determinístico; o modelo não executa shell.

Gemma usa [termos próprios](https://ai.google.dev/gemma/terms), diferentes das licenças
do software. Não redistribuímos pesos neste repositório. Não há fine-tuning nem promessa
de equivalência a modelos de fronteira. O 355M não foi selecionado: aumentar GPT-2
não resolveria sua falta de treinamento para conversa em português.

## Backend histórico: OpenAI GPT-2 124M

As seções seguintes descrevem o backend preservado `gpt2`, CPU float32. Nenhum peso
OpenAI foi treinado, refinado ou melhorado; contexto em português não transforma
GPT-2 em modelo de instruções.

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
