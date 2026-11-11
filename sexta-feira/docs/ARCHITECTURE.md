# Arquitetura SEXTA-FEIRA

Assistente pessoal experimental com API modular em um processo, um worker de
inferência e threads HTTP limitadas. O backend atual usa um segundo processo nativo
llama.cpp para manter uma única instância quantizada do Gemma; o serviço supervisor
garante seu ciclo de vida Windows. Não há API comercial de inferência, telemetria
ou execução de shell pelo modelo. Não há dependência de infraestrutura distribuída.

| Subsistema | Implementação | Responsabilidade |
|---|---|---|
| Core | `cli.py`, `settings.py`, `scripts/service_runner.py` | Inicialização, configuração, encerramento |
| Inferência atual | `brain.py`, `inference_llama.py`, `scripts/native_runner.py` | CPU, Gemma GGUF, loopback autenticado, fila, limites |
| OpenAI preservada | `inference_torch.py`, `weights.py`, tokenizador original | GPT-2, checkpoint original, alternativa histórica |
| Memory | `storage.py` | SQLite, histórico e memórias explicitamente salvas |
| Task | `storage.py`, `tools.py` | Tarefas e estado de conclusão |
| Voice | `web/app.js` | Vozes locais do dispositivo; reconhecimento não ativado |
| Tools | `tools.py` | Operações determinísticas em uma lista permitida |
| API | `server.py` | REST `/api/v1`, validação e OpenAPI |
| Web | `web/` | HTML/CSS/JS sem CDN e sem Electron |
| Security | `security.py`, `server.py`, ACL Windows | Credenciais, sessões, papéis, origem e limites |
| Observability | `observability.py`, métricas da API | Recursos e logs rotativos sem conversas |

## Modelo e procedência

O código TensorFlow histórico da OpenAI permanece em `openai-gpt2/`; uma cópia
pristine e as diferenças documentadas permitem auditar as modificações.
O backend histórico usa um adaptador PyTorch próprio da arquitetura GPT-2. Ele
não executa o grafo TensorFlow original. O leitor de checkpoint suporta apenas
o formato limitado do checkpoint público e não desserializa pickle nem código.

O download separado usa o domínio HTTPS original
`openaipublic.blob.core.windows.net/gpt-2/models/124M/`. Os arquivos TensorFlow
ficam preservados. Tamanho, Content-MD5 e SHA-256 fixados para 124M verificam
integridade; o recibo local também é conferido antes da carga. Os SHA-256 foram
medidos por este projeto a partir da origem HTTPS, não publicados como uma
assinatura criptográfica independente da OpenAI.
O processo de inferência exige os arquivos verificados e não baixa modelos.

As alterações de software não treinam o modelo nem aprimoram seus pesos.
Português e instruções são limitados pelo GPT-2 original. O prompt personaliza
o contexto, mas não garante que o modelo siga a personalidade ou diga a verdade.

## Recursos e concorrência

Padrão: 124M, CPU, uma thread de matemática, uma inferência ativa, duas na fila,
512 tokens de entrada e até 64 novos tokens. O limite arquitetural é de 1024
posições. A reserva de RAM protege os demais aplicativos e a inicialização
recusa recursos insuficientes. Não existe um limite rígido de memória do Windows
no processo: a proteção é preventiva e precisa de medições no servidor real.

Timeout e cancelamento são cooperativos entre passos. Uma operação nativa de
PyTorch em andamento precisa retornar antes de observar o cancelamento. Falhas
repetidas ativam espera antes de nova tentativa. A troca de modelo exige reinício
controlado; 355M requer escolha explícita e ainda precisa de benchmark no destino.
GPU, quantização e reconhecimento Whisper não são ativados automaticamente.

## Dados e autoridade

Histórico é dado pessoal persistido para consulta, distinto de memória explícita.
O prompt usa apenas poucas mensagens recentes e memórias com correspondência
textual. Preferências, tarefas e sessões ficam no SQLite próprio, com WAL,
transações, foreign keys e busy timeout. Cópias de segurança usam a API de backup
SQLite; restauração exige validar integridade e preservar o original.

Apenas endpoints determinísticos executam ferramentas. Texto produzido pelo
GPT-2 não é interpretado como comando, alteração administrativa ou ação concluída.
Os clientes autenticados acessam o mesmo espaço pessoal do proprietário; não há
isolamento multiempresa nem cadastro de usuários independentes.

## Fronteira de rede

O serviço deve escutar em `127.0.0.1:8765`. A implantação inicial deve usar um
Cloudflare Tunnel existente somente depois de auditar e preservar suas rotas,
com HTTPS externo e política Access configurada pelo proprietário. A configuração
da aplicação aceita uma origem HTTPS exata; não existe CORS curinga.

As credenciais são Bearer explícitas, nunca query strings ou cookies. Assim o
navegador não anexa autenticação automaticamente em requisições CSRF. O login
gera sessão com expiração e revogação. A credencial de bootstrap permite obter
sessão administrativa e deve permanecer em arquivo com ACL restrita.

O servidor HTTP stdlib foi mantido para reduzir dependências. Seu uso externo
depende do proxy protetor e de testes no destino; os limites de conexão, corpo,
origem e taxa são defesa adicional, não substituem HTTPS e Access.
