# SEXTA-FEIRA — OpenAI GPT-2 privado

Assistente pessoal experimental, modificável, com inferência local gratuita em CPU. O motor usa os pesos **OpenAI GPT-2 124M originais**, preservados no formato TensorFlow e lidos por um adaptador PyTorch próprio. Não utiliza API comercial, Ollama, Transformers, serviços pagos de inferência ou modelos de outras empresas.

**GPT-2 não é um chatbot moderno.** A geração em português pode ser incoerente, incorreta ou não seguir instruções. Os pesos não foram treinados nem melhorados. Memória, tarefas, autenticação e ferramentas são software determinístico externo ao modelo. Texto gerado não comprova uma ação realizada.

## O que está implementado

- API REST privada `/api/v1`, Bearer obrigatório, sessões com expiração e revogação, papéis usuário/admin, OpenAPI autenticado, validação de origem/host e limites.
- SQLite próprio com histórico, memórias explícitas editáveis/excluíveis, tarefas, preferências, exportação limitada, backup consistente e verificação de integridade.
- Interface HTML/CSS/JS escura, responsiva, sem CDN, com estado real do modelo, fila e métricas administrativas. Token somente na memória da página.
- Voz com sintetizadores locais em português do navegador, quando disponíveis. Microfone desativado; Whisper ainda não instalado nem validado.
- Carga única sob demanda, uma inferência por vez, fila de duas, uma thread CPU, 512 tokens de entrada, até 64 novos, timeout e reserva preventiva de RAM.
- Instalador Windows isolado, diagnóstico privado, logs rotativos, preparação de serviço LocalService via WinSW e procedimento de atualização/reversão.

**Estado em 11/11/2026:** instalação privada em Windows Server 2022 executada, serviço LocalService via WinSW funcionando e hostname HTTPS com autenticação própria verificado. Os 49 testes passaram no destino, incluindo os cinco testes com pesos reais. Cloudflare Access e a checagem adicional de persistência após um novo reinício completo dos dois serviços continuam pendentes. Consulte o [registro de validação](docs/VALIDATION.md); inventários, credenciais e relatório operacional detalhado ficam fora do Git.

## Instalação Windows

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
