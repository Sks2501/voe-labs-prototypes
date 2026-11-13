# SEXTA-FEIRA — assistente privada local

Assistente pessoal experimental, modificável, com inferência local sem cobrança por mensagem. Após os resultados incoerentes do GPT-2 e a autorização posterior do proprietário para fazer o possível sem pagar, a instalação atual usa **Gemma 3 4B IT Q4_K_M**, executado por **llama.cpp em CPU no Dell**. Não usa API comercial nem Ollama. O navegador é apenas cliente da API; não executa o modelo.

O código original OpenAI, sua licença, as adaptações e os pesos **GPT-2 124M** continuam preservados para estudo e reversão. O novo modelo é da Google, com quantização de ggml-org e termos próprios; não foi treinado por este projeto. Não é equivalente a um modelo de fronteira como o Astra. Memória, tarefas, autenticação e ferramentas são módulos externos; texto gerado não comprova uma ação executada. Veja [origem e licenças](docs/THIRD_PARTY.md).

## O que está implementado

- API REST privada `/api/v1`, Bearer obrigatório, sessões com expiração e revogação, papéis usuário/admin, OpenAPI autenticado, validação de origem/host e limites.
- SQLite próprio com histórico, memórias explícitas editáveis/excluíveis, tarefas, preferências, exportação limitada, backup consistente e verificação de integridade.
- Interface HTML/CSS/JS escura, responsiva, sem CDN, com estado real do modelo, fila e métricas administrativas. Token somente na memória da página.
- Conversas separadas na lateral, títulos editáveis, contexto por conversa e perfil explícito em **Sobre você**. Estilo inspirado na SEXTA-FEIRA, sem capacidades fictícias. Veja [conversas e personalização](docs/CONVERSATIONS.md).
- Cliente Android leve em [android/](android/README.md), com visual Liquid Glass opcional, voz local e exportação nativa. O modelo continua no servidor; não inclui token ou recursos completos do aplicativo oficial do ChatGPT.
- Voz com sintetizadores locais em português do navegador, quando disponíveis. Microfone desativado; Whisper ainda não instalado nem validado.
- Uma instância nativa do modelo, uma inferência por vez, fila de duas, duas threads CPU, contexto total 2048, entrada até 1536 e geração até 192 tokens. Timeout de 90 s e reservas preventivas de RAM; prioridade BelowNormal.
- Instalador Windows isolado, diagnóstico privado, logs rotativos, preparação de serviço LocalService via WinSW e procedimento de atualização/reversão.

**Estado em 11/11/2026:** modelo nativo, API e túnel exclusivo em serviços LocalService no Windows Server 2022. O proprietário voltou a solicitar acesso pelo site já existente, e o túnel exclusivo foi reativado. Interface e API em `https://sexta.teambike.online`, autenticadas; os serviços de produção não foram reiniciados. O cliente REST/SSH continua disponível. Consulte o [registro de validação](docs/VALIDATION.md); credenciais e inventários ficam fora do Git.

## Usar somente a API

No servidor: `http://127.0.0.1:8765/api/v1`, com `Authorization: Bearer <token privado>`.
Conversa: `POST /conversations`, JSON `{"message":"Olá"}`. A resposta inclui `reply`,
`source`, `generated` e `action_executed`. Comandos como `/hora` são ferramentas;
mensagens normais são processadas pelo modelo local configurado. A fonte atual é `local_model`; a resposta informa também o modelo.

`scripts/api_client.py` usa somente a biblioteca padrão Python. O arquivo privado
de configuração indica `token_file`, `base_url` e `transport: "http"`. Exemplo:

```powershell
python scripts\api_client.py --config 'CAMINHO_PRIVADO\api-client.json' health
python scripts\api_client.py --config 'CAMINHO_PRIVADO\api-client.json' chat '/hora'
python scripts\api_client.py --config 'CAMINHO_PRIVADO\api-client.json' request GET tasks
```

Para outro computador com SSH já autorizado, o transporte `ssh` recebe no JSON
privado os campos `ssh_host`, `ssh_key`, `known_hosts`, `remote_python` e
`remote_client`. O fingerprint precisa estar previamente verificado. O cliente
executa somente o comando fixo do cliente remoto e envia token/corpo por stdin
criptografado, sem credenciais nos argumentos, port forwarding ou DNS. O serviço
HTTP continua no loopback do servidor; `127.0.0.1` de outro PC não aponta para ele.
O modo `request` aceita `--json-file` para corpos; `chat` sem argumento lê stdin.

## Instalação Windows

Os comandos abaixo preparam a base histórica GPT-2. Para adicionar o backend moderno a um runtime já identificado, siga [operação do modelo moderno](docs/LOCAL_MODEL_WINDOWS.md). Não execute novamente o provisionamento para atualizar uma instalação existente.

Python x64 3.11–3.13, pelo menos 5 GB livres no volume escolhido e margem de RAM para os demais serviços. A instalação não substitui Python global nem serviços da Team Bike. Use diretórios exclusivos; consulte [operação Windows](docs/WINDOWS.md) antes de executar no servidor compartilhado.

```powershell
.\scripts\audit.ps1
.\scripts\install.ps1 -Python 'C:\Python311\python.exe' -RuntimeRoot 'C:\SextaFeiraRuntime'
.\scripts\start.ps1 -RuntimeRoot 'C:\SextaFeiraRuntime'
```

O caminho Python é exemplo: use um interpretador x64 realmente instalado e acessível à conta de serviço. Os scripts recusam uma porta ocupada e não encerram seu proprietário. Os wrappers `.bat` são atalhos para os mesmos scripts.

Como alternativa sem instalar Python global, `scripts/provision.ps1 -RuntimeRoot 'C:\SextaFeiraRuntime' -InstallService` prepara Python 3.13.15 portátil oficial, com tamanho/hash fixados, instala e testa o sistema, verifica WinSW 2.12.0 e ativa somente o serviço próprio. Requer execução administrativa para registrar o serviço; a operação diária usa LocalService. Não publica o hostname automaticamente. `-PrepareOnly` verifica apenas o Python portátil.

O instalador baixa PyTorch do índice CPU oficial, aplica versões de `requirements.txt` e `constraints.txt`, baixa os sete arquivos da origem oficial OpenAI e verifica seus hashes. Banco, modelos, token, logs e relatórios ficam no runtime privado, fora do Git. A execução normal nunca baixa modelos.

Abra `http://127.0.0.1:8765`, obtenha o token em `data\access.token` por um editor local autorizado e inicie uma sessão. Use papel usuário no cotidiano; admin para métricas, backup e administração de sessões. Não coloque o token em comandos, capturas, GitHub ou documentos. O `init` aplica uma DACL privada no Windows.

## Desenvolvimento e testes

Com as variáveis `SEXTA_DATA_DIR` e `SEXTA_MODEL_DIR` apontando para diretórios privados do ambiente de teste:

```powershell
python -m sexta_feira init
python -m sexta_feira download --model small
python -m sexta_feira verify-model --model small
python -m unittest discover -s tests -v
$env:SEXTA_RUN_MODEL_TESTS='1'
python -m unittest discover -s tests -v
python scripts\smoke.py
python -m sexta_feira serve --token-file 'CAMINHO_PRIVADO\access.token'
```

Sem `SEXTA_RUN_MODEL_TESTS=1`, os cinco testes do checkpoint real são ignorados explicitamente. Para registrar saída em Windows PowerShell 5.1, use `python scripts\run_tests.py`, que envia o progresso normal para stdout. O smoke utiliza banco temporário e não altera conversas existentes. Os resultados locais estão em [validação](docs/VALIDATION.md) e [benchmark](docs/benchmark-local.json). Os tempos do computador de desenvolvimento não são medições do servidor.

## Rede, segurança e manutenção

O servidor escuta somente em loopback. O uso móvel depende de HTTPS e acesso protegido; o roteiro para `sexta.teambike.online` está em [Cloudflare](docs/CLOUDFLARE.md). Não exponha a porta 8765 diretamente e não substitua rotas existentes. Nenhuma publicação de DNS ou Tunnel é automática.

SQLite não é criptografado pelo aplicativo. A proteção em repouso depende de ACL, conta Windows e, se exigido pelo proprietário, criptografia de disco do sistema. Backups/exportações continuam sendo dados privados. O projeto é para um proprietário e seu espaço pessoal compartilhado com clientes autorizados; não oferece isolamento multiempresa.

Histórico é persistido separadamente de memórias explicitamente salvas. Apenas poucas mensagens e memórias pertinentes entram no contexto. Memórias e tarefas têm limites conservadores, com erro explícito ao atingir o limite; histórico possui consulta paginada e exclusão. Backups não são enviados à nuvem.

Atualizações exigem backup, revisão de versões e testes antes de parar somente a SEXTA-FEIRA. Dados/configuração são preservados e há roteiro de reversão em [Windows](docs/WINDOWS.md). Não existem atualizações automáticas de dependências.

## Origem e licença

Fonte histórica: [openai/gpt-2](https://github.com/openai/gpt-2). O código original, a licença MIT modificada e uma cópia pristine estão acessíveis em `openai-gpt2/`. [Detalhes de inferência](docs/INFERENCE.md) registram commit, hashes, alterações e seus testes. [Arquitetura](docs/ARCHITECTURE.md) descreve as fronteiras dos módulos e os limites operacionais.

SEXTA-FEIRA é uma personalização independente; não é produto oficial da OpenAI nem equivalente ao ChatGPT. Preserve atribuições e identifique os textos gerados.
# Pesquisa pessoal e manutenção

Use **+ → Pesquisar na web**, `/pesquisar assunto` ou `/site https://site-publico/`. A resposta informa fontes e data; a síntese permanece no modelo local. Não há garantia de correção factual ou cobertura de todos os sites. [Como funciona e limites](docs/WEB_RESEARCH.md).

O servidor tem um [procedimento de organização reversível](docs/MAINTENANCE.md) para instaladores próprios antigos e um índice privado de operação. Não reorganiza pastas de produção automaticamente.
