# Validação — desenvolvimento e implantação privada

## Atualização de implantação — 11/11/2026

### Alteração posterior: API sem publicação externa

Por orientação posterior do proprietário, o serviço dedicado `SextaFeiraTunnel`
foi parado e desabilitado. `SextaFeira` e o `Cloudflared` de produção permaneceram
em execução. Não foi criado outro hostname, rota, serviço ou abertura de firewall.
O registro DNS anterior foi preservado, mas o túnel exclusivo não publica mais a
aplicação. Os testes HTTPS abaixo são históricos, anteriores a essa alteração.

O cliente `scripts/api_client.py` foi instalado e testado: saúde autenticada por
HTTP loopback no servidor; saúde, `/hora` e uma geração real GPT-2 a partir do
computador cliente via SSH, todos HTTP 200. JSON UTF-8 e credenciais são enviados
por stdin criptografado, com chave/fingerprint já configurados, sem usar subdomínio
ou ativar encaminhamento de portas. A resposta portuguesa do modelo continuou
incoerente; isso não foi apresentado como melhoria dos pesos ou qualidade.

### Implantação e ensaios anteriores no mesmo dia

O acesso administrativo por SSH foi estabelecido com chave, fingerprint conferida
no RDP e restrição ao cliente observado. A auditoria CIM foi executada no destino,
com inventário privado de serviços, portas e recursos antes da instalação.

Python portátil oficial 3.13.15 e WinSW 2.12.0 foram verificados por tamanho/hash.
O provisionamento instalou dependências CPU, baixou e verificou os sete arquivos
oficiais do GPT-2 124M, inicializou SQLite privado e executou inferência real.
Depois da correção da saída de unittest para stdout no PowerShell 5.1, a instalação
e o smoke passaram. Os **49 testes, incluindo os cinco testes com pesos reais,
passaram sem ignorados em 8,271 s** no ensaio adicional do servidor.

Os serviços próprios `SextaFeira` e `SextaFeiraTunnel` estão em execução como
LocalService, com inicialização automática, logs rotativos e recuperação limitada.
O serviço da aplicação foi parado/iniciado com sucesso ao aplicar a origem HTTPS,
antes da criação do serviço de túnel dependente. O túnel de produção não foi
reiniciado; seus processos e os listeners de produção comparados mantiveram os
mesmos PIDs. Inventários e medições detalhadas do host não são publicados no Git.

Pelo hostname HTTPS foram verificados: saúde autenticada, bloqueio 401 sem
credencial/inválida, origem indevida 403, usuário sem acesso administrativo,
revogação de sessão, memória/correção/exclusão, tarefa/conclusão/exclusão,
histórico, exportação, backup, integridade SQLite, OpenAPI 3.1 e quatro gerações
reais. Duas chamadas simultâneas foram atendidas pela fila serializada. O login
da interface publicada e `/hora` foram testados em navegador; viewport 390×844
não apresentou overflow horizontal. A sessão de teste foi encerrada e os registros
de memória/tarefa criados pelo verificador foram removidos. A geração em português
continuou incoerente: execução correta não equivale à qualidade de um chatbot atual.

Pendências atuais: Cloudflare Access não configurado; proteção externa usa a
autenticação própria por Bearer e sessões expirantes. O teste adicional de
persistência após parar/reiniciar os dois serviços já interdependentes foi
bloqueado pela revisão automática de execução, sem motivo específico informado;
não foi executado nem marcado como aprovado. Recuperação automática após falha
forçada e reboot do servidor não foram testados. Não houve reboot. A persistência
foi conferida por novo cliente e pelos testes de SQLite/backup. O fetch do hostname
por uma ferramenta web externa falhou; HTTPS e a interface foram validados a partir
da infraestrutura disponível, sem comprovar um teste por rede móvel independente.
Voz audível, Whisper, 355M, quantização e GPU continuam não validados.

O código e os serviços estão operacionais, com essas verificações de implantação
explicitamente pendentes. O relatório completo e as capturas ficam na entrega
privada local. Nenhum token, banco, peso ou inventário administrativo foi incluído
nos commits.

## Registro histórico — desenvolvimento de 10/11/2026

As seções abaixo documentam o estado naquele dia. Pendências de acesso e instalação
desse registro foram superadas pela atualização acima, onde indicado.

## Escopo e ambiente

O desenvolvimento e os testes foram executados em **Windows 11 Pro**, i5-4570,
quatro núcleos/lógicos, 11,92 GiB de RAM visível, Python 3.13.15 x64 e PyTorch
2.9.1+cpu. Não confundir estas medições com o servidor de destino. A unidade C:
tinha aproximadamente 660 MiB livres no início; dependências, pesos, SQLite e
temporários foram mantidos em runtime isolado na unidade G:. Nenhum aplicativo
existente foi encerrado para liberar RAM ou disco.

O RDP aberto foi observado visualmente: Windows Server 2022 Datacenter Evaluation,
i5-7200U, 2 núcleos/4 processadores lógicos, 16 GB instalados, 15,9 GB utilizáveis,
cerca de 11,8 GB disponíveis e disco de 111 GB com 78,4 GB livres naquele momento.
O Gerenciador de Tarefas mostrava Intel HD Graphics 620 e cloudflared em execução;
as janelas existentes indicavam aplicações Team Bike nas portas locais 3333/3334.
A NVIDIA não apareceu nessa visualização. Isso não comprova ausência física da
940MX, VRAM, modelo Dell ou instalação bare metal. A auditoria completa por CIM no
servidor permanece pendente. “Virtualization: Enabled” no Gerenciador de Tarefas
também não distingue, sozinho, um host de um convidado.

Há RDP ativo, mas nenhuma sessão shell remota foi estabelecida. As verificações
de conectividade SSH/WinRM não tiveram sucesso. Não foram usados nem publicados
segredos do servidor. Não houve comandos, instalação, alteração de serviço,
firewall, banco PostgreSQL ou rota de Tunnel no servidor remoto.

## Resultados

| Verificação | Evidência e resultado real |
|---|---|
| Instalação de dependências | Venv isolado criado; CPU wheel oficial; versões fixadas; `pip check` passou |
| Instalador completo | `scripts/install.ps1` executado no runtime de desenvolvimento; relatório privado marcou dependências, pesos, banco, testes e inferência aprovados; serviço não instalado e Cloudflare não alterado |
| Testes automatizados | **49 testes passaram, nenhum ignorado**, com `SEXTA_RUN_MODEL_TESTS=1`, em 29,256 s no ensaio completo |
| Origem e integridade | Sete arquivos oficiais 124M locais; tamanho/MD5/SHA256 e cópia original do código conferidos; alteração simulada de peso foi detectada |
| Inferência real | Checkpoint carregado e 64 tokens gerados em CPU; smoke HTTP real passou em 10,702 s, incluindo preparação e chamada; etapa de inferência reportou 9,243 s nesse smoke |
| Compatibilidade numérica | Tokenização UTF-8 contra original; logits contra NumPy independente: erro absoluto máximo 3,8147e-5, mesmo top-1; cache KV contra contexto completo: 6,1035e-5 |
| Concorrência e recursos | Carga concorrente única, fila cheia, cancelamento antes/durante, timeout, reserva de RAM e encerramento testados; cargas sintéticas pequenas, sem teste na produção |
| Persistência | Histórico transacional, migração sem perda, esquema futuro recusado, quatro writers, memórias/tarefas com caps atômicos e paginação de dados legados |
| Autenticação | Ausência de credencial bloqueada; sessões expiram/revogam; usuário não acessa admin; credenciais não aparecem no SQLite ou logs operacionais |
| Limites HTTP | Corpo/tipos/esquemas/origem/Host, taxa, conexões, fila, exportação de uma vez e tamanho máximo testados |
| Backups | Backup consistente, integridade e recuperação em outro arquivo testados; limite e criação serializada |
| Arquivos Windows | ACL real testada; permissão explícita Everyone foi removida de arquivo de teste; diretório alheio recusado sem mudança; token preservado em reinicialização |
| Ferramentas | Comandos explícitos executam ferramentas reais; saída do GPT-2 contendo comando nunca é executada |
| Interface desktop | Login admin, memória, tarefa/conclusão, conversa real, histórico persistente após reinício e `/hora` com origem “Ferramenta local” verificados no Chrome |
| Interface móvel | Viewport 390×844: largura útil 375 px e scrollWidth 375 px, sem overflow horizontal; captura visual salva localmente |
| Voz | Voz local em português detectada no navegador; síntese audível não testada; microfone não capturado |
| Ciclo Windows | Runner em primeiro plano iniciou, encerrou por evento Windows e iniciou novamente; saúde autenticada e histórico persistido verificados; isto não é teste do serviço SCM/WinSW |
| Scripts | JavaScript passou em `node --check`; scripts PowerShell passaram no parser; Python moderno e arquivos legados passaram em compilação sintática |
| Proteções de instalação | C: sem 5 GB livres foi recusado; descoberta escolheu Python 3.13 local; registro de serviço com Python per-user foi bloqueado antes de mudanças |
| Serviços existentes | Nenhuma alteração administrativa foi realizada no servidor; disponibilidade funcional completa antes/depois ainda precisa ser medida no destino |

O relatório de instalação contém o commit-base anterior às alterações; a execução
ocorreu sobre a árvore de trabalho modificada que foi publicada nesta ramificação.
Os arquivos privados de diagnóstico não fazem parte do repositório.

## Desempenho medido

[benchmark-local.json](benchmark-local.json) registra medição separada com uma
thread CPU: carga 2,625 s; geração de 64 tokens em 3,923 s (inglês) e 4,113 s
(português), aproximadamente 15,6–16,3 tokens/s. RSS após carga: 724.189.184 bytes;
pico na repetição: 741.384.192 bytes, aproximadamente 707 MiB. CPU nesses ensaios:
3,875 s e 4,063 s. Outros aplicativos permaneceram em execução.

Pesos e metadados: 499.735.887 bytes. Venv medido: 627.920.804 bytes. A reserva
mínima de 5 GB do instalador cobre preparação e margem; não é uma reserva permanente
de todo esse espaço. Não há benchmark do i5-7200U nem aprovação do 355M.

Uma resposta real em português foi incoerente, misturando idiomas. Portanto,
o sucesso de inferência comprova execução local e compatibilidade técnica, não
qualidade de assistente, raciocínio ou confiabilidade factual. As ferramentas
determinísticas permanecem disponíveis sem carregar o modelo.

## Pendências registradas em 10/11/2026 (histórico)

- Auditar o servidor por CIM, confirmar fabricante/virtualização/afinidade/VRAM,
  inventariar todos os serviços/portas e preservar configuração privada do Tunnel.
- Preparar Python x64 acessível a LocalService no destino, executar instalador e
  medir RAM/CPU/latência junto às cargas Team Bike.
- Obter WinSW oficial com checksum confiável; registrar e testar SCM como
  LocalService, inicialização automática, Stop/Start e recuperação de falhas.
- Inspecionar rotas Cloudflare existentes, configurar Access e somente então
  adicionar o hostname exclusivo; testar de rede externa e validar a produção.
- Testar síntese no dispositivo final; Whisper e reconhecimento local permanecem
  desativados. Não há troca silenciosa para reconhecimento externo.
- Implementar notificações agendadas/compromissos estruturados em etapa posterior;
  nesta versão tarefas são registros explícitos, sem scheduler.
- Persistir a origem de cada resposta no histórico em futura migração; a resposta
  JSON atual identifica fonte, e a UI conserva o rótulo apenas na sessão da página.
- Validar Python 3.11/3.12 em execução, TensorFlow 1.x, 355M, quantização e GPU se
  houver motivo medido; não foram testados aqui.
- Cancelamento REST por desconexão do navegador não foi validado; o motor possui
  cancelamento cooperativo e deadline que inclui a espera na fila.

Naquela data, os critérios completos de implantação não tinham sido alcançados.
O código e a instalação de desenvolvimento estavam validados; a implantação no
servidor dependia de acesso administrativo executável e dos testes acima.

## Histórico de engenharia

Correção posterior para entrega por ZIP: validada em Windows PowerShell 5.1.
Pacotes sem `.git` registram `source-package` sem abortar a instalação; metadados
de repositórios ancestrais são ignorados. A descoberta de Python foi confirmada
quando somente 3.13 está disponível. O wrapper BAT conserva a janela aberta para
leitura do resultado. Não houve nova instalação ou carga de modelo nesses testes.

Ramificação autorizada: `sexta-feira-openai-gpt2`; alterações limitadas ao
diretório `sexta-feira/`. A ramificação `main` não foi alterada.

- `49d3f59`: origem OpenAI preservada, adaptador CPU, checkpoint e testes reais.
- `eb20358`: API autenticada, persistência limitada, ferramentas e proteção Windows.
- `1f19f93`: interface responsiva, diagnóstico e instalação/serviço Windows.
- O commit de documentação subsequente reúne arquitetura, operação e este relatório.

Modelos grandes, banco, tokens, configurações privadas e relatórios de inventário
não integram os commits. As capturas de teste ficam no pacote de entrega local.
