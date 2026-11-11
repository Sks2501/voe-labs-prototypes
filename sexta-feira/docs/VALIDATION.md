# Validação — desenvolvimento e implantação privada

## Atualização de implantação — 11/11/2026

### CPU, RAM e disco disponíveis para o proprietário

O endpoint autenticado `/hardware` e a ferramenta `server_hardware` foram implantados. Sessão user agora pode consultar uso total de CPU, RAM total/usada/disponível, RAM da IA/API e disco; `/metrics` continua exclusivo de admin. A saída permitida exclui PIDs, caminhos, portas, contadores administrativos e credenciais. O painel atualiza a cada 10 s enquanto visível. Solicitações operacionais diretas usam a ferramenta, sem gerar números pelo modelo.

No servidor, 80 testes descobertos: 75 passaram e cinco testes históricos de checkpoint opt-in foram ignorados. Passaram cálculo de CPU (kernel inclui idle), primeira amostra, métricas filtradas, ferramentas sem argumentos, autenticação user, proteção admin e regressões. JavaScript passou sintaxe e oito verificações de renderização segura. Não foi realizado teste de carga nem nova inferência nesta alteração.

No HTTPS real, verificados login user, painel, atualização automática entre duas amostras, capacidades e uso de RAM/disco, leitura de CPU, requisição natural pelo chat, origem recusada, falta de autenticação recusada, `/metrics` recusado para user e logout. Viewports 390 × 700 e 360 × 640 sem transbordamento horizontal. Não houve teste físico em Android. Serviços/portas de produção e processo de inferência permaneceram com as mesmas identidades durante o deploy; apenas serviços próprios de API/túnel foram reiniciados. Backup consistente privado preservado.

O provedor CPU opcional foi preparado no servidor: ZIP LibreHardwareMonitor 0.9.6 e instalador PawnIO 2.2.0 com SHA-256 conferidos, Authenticode válido do instalador e biblioteca .NET 0.9.6.0 carregada sem abrir hardware. A configuração ficou desativada, sem driver instalado. **Temperatura interna de CPU ainda não validada: ativação depende da autorização específica solicitada ao proprietário.** Não se declara temperatura de RAM/GPU ou acesso irrestrito ao hardware. Veja [TEMPERATURES.md](TEMPERATURES.md).

### Sensores de temperatura do servidor

Ferramenta `/temperaturas`, endpoint Bearer `/api/v1/temperatures`, botão no chat e painel de sensores implantados. O coletor isolado usa provedores nativos Windows, a cada minuto, sem driver adicional; a API continua LocalService. Foram confirmadas leituras de disco e zona ACPI, sem atribuir a zona à CPU nem classificar o equipamento como normal. CPU, GPU, RAM, placa-mãe e bateria continuam indisponíveis nesta integração.

No servidor, a suíte passou: 75 testes descobertos, 70 executados e cinco testes históricos de checkpoint opt-in ignorados. Nenhuma nova carga de modelo foi necessária. Passaram validação de snapshot ausente, futuro, antigo, inválido e excessivo; rejeição de comandos/parâmetros; autenticação; sessão user; consulta no chat sem chamar o modelo; OpenAPI; persistência e regressões existentes. JavaScript passou sintaxe e oito verificações de renderização segura.

A primeira coleta funcionou; a verificação da coleta seguinte encontrou conversão indevida de `$null` para caminho vazio em `File.Replace` no PowerShell 5.1. Corrigida com `[NullString]::Value`, validada por duas gravações consecutivas, execução SYSTEM e disparo automático posterior com resultado zero. A reinstalação também encontrou caminho COM com barra final; corrigido e validado por reinstalação idempotente. Coletas recentes demoraram cerca de 1,6 s, sem processo de sensores residente entre disparos.

Login, botão Temperaturas, resposta determinística, painel e logout foram verificados no HTTPS, em viewport de 390 × 700, sem transbordamento horizontal. Não houve teste em aparelho físico Android nesta etapa. Aplicações de produção, banco e túnel preexistente mantiveram PIDs/portas durante a atualização; apenas API/túnel próprios foram reiniciados. Backup consistente do SQLite e cópia dos arquivos anteriores permaneceram privados no runtime. Temperaturas e credenciais não integram os registros públicos de validação.

Para limites e manutenção: [TEMPERATURES.md](TEMPERATURES.md). Sensores internos adicionais exigem avaliação separada de provedor/driver e autorização adequada. O reconhecimento de voz e a proteção Cloudflare Access continuam fora desta alteração.

### Revisão 1.0.1 — visual móvel neutro e tema do sistema

Após o feedback sobre o visual, foi usada a [referência móvel oficial](https://chatgpt.com/download/)
para reorganizar controles compactos, fundo neutro, menus modais e compositor de uma
linha. Foram removidos os gradientes azul/roxo e a decoração da conversa. A marca
permanece SEXTA-FEIRA. O usuário escolheu acompanhar o tema do telefone; esse é o
padrão, com seleção clara/escura opcional. A escolha visual continua apenas local.

O APK 1.0.1/versionCode2 foi compilado e verificado, usando a mesma identidade de
assinatura da 1.0.0. SHA-256:
`1466ddba3aa266b90b7555cce4271bf99d48c80f363d0eb054f6e19ccfc5101d`.
As assinaturas v2/v3, alinhamento e 14 casos de origem passaram. O recibo público
foi atualizado, e o APK 1.0.0 foi preservado no runtime. O novo bridge informa
apenas o tema do sistema e ajusta cores/barras; não aumenta permissões.

Quatro testes de regressão de download/manifesto passaram no servidor em 0,336 s.
O parser de respostas passou oito verificações Node de segurança/formatação, incluindo
HTML tratado como texto, blocos de código incompletos e rótulo UTF-8. JavaScript passou
checagem de sintaxe; os 80 IDs HTML são únicos. Não foi repetida inferência de modelo
ou a suíte Python completa porque esses componentes não mudaram.

No navegador HTTPS, login/logout, nova conversa, menus, comando real `/hora`, tema
claro, tema do sistema e formatação de código foram conferidos. Em 390×700 e 360×640
não houve overflow horizontal; o compositor permaneceu dentro do viewport. Uma
fixture explicitamente sintética foi usada para verificar código/texto literal,
sem inferência: um bloco de código e zero elementos HTML perigosos na resposta.
Os registros dessa conversa de QA foram removidos somente após conferir seu conteúdo;
integridade final `ok`. Sessões de teste foram revogadas, sem erros JavaScript capturados.

Download público HTTPS conferido novamente por versão, tamanho e hash. O modelo
nativo e os serviços Team Bike foram preservados. Instalação física, mudança real de
tema no Android e teclado/voz do aparelho continuam pendentes de teste no dispositivo.
As capturas mostram o frontend responsivo, não uma execução nativa em iPhone.

### Android e Liquid Glass — revisão posterior

O proprietário pediu APK Android para download e confirmou o visual Liquid Glass.
Foi criado um cliente WebView Java/API26+, com origem HTTPS restrita, sem modelo ou
token embutido, sem microfone/câmera/contatos e sem bibliotecas de publicidade.
Ponte nativa limitada a voz local e exportação com seletor do Android; não oferece
shell, leitura arbitrária de arquivos ou acesso a credenciais.

O SDK existente compilou o APK 1.0.0 universal, **25.221 bytes**, minSDK26/target35.
`apksigner` verificou assinaturas v2/v3; `zipalign` e manifesto passaram. Os 14 casos
da política de origem passaram em Java. SHA-256 do APK distribuído:
`bdeef54e9a0c827102230e860a4a17c4b3c510b3b4e0b9ad1455df26782ca5b0`.
Certificado público SHA-256:
`7ec80c56c4d5ecacd203cd3e6a78150384857ebdc6d3d7b3319f741e87868e60`.
Chave/senha ficaram em diretório privado com ACL/DPAPI, fora do Git e servidor web.

Os **69 testes Python passaram no Dell em 10,440 s**, sem ignorados, incluindo
quatro testes de download GET/HEAD, manifesto, hash, caminho e proteção da API.
O download HTTPS real foi lido sem autenticação e seu tamanho/MIME/hash conferidos.
Uma requisição com formato de User-Agent WebView retornou 200; isso não equivale
a executar o APK em um aparelho. A API privada continua bloqueando acessos sem token.

No navegador 390×700 foram conferidos landing de download, login, aparência de vidro,
menu e compositor sem overflow horizontal. Tema de vidro terminou com compositor em
700 px e largura 390 px. Sem erros JavaScript capturados; sessão de QA revogada.
O tema padrão do APK é vidro e pode ser trocado nos Ajustes. Só a escolha visual é
persistida localmente; token continua na memória da página. O teste é do frontend,
não uma captura nativa de Android.

Houve backup consistente e atualização somente do projeto. Modelo nativo, túnel de
produção e serviços Team Bike foram preservados. Não foi criada outra rota DNS,
porta pública ou recurso pago. `/android` e o instalador são públicos por autorização
do proprietário, sem conter credenciais ou acesso aos dados pessoais.

Não havia Android conectado e nenhuma instalação física foi realizada. TTS audível,
file picker, teclado/insets, rotação e ciclo de vida em aparelho ainda precisam de
teste no dispositivo. A compilação não foi apresentada como comprovação dessas
funções. O APK não inclui todas as capacidades do ChatGPT ou da personagem fictícia.

### Revisão posterior: conversas e personalização

O proprietário pediu interface com padrão visual de chat, comportamento inspirado
na SEXTA-FEIRA e contexto pessoal explícito. A revisão criou lateral de conversas,
gaveta móvel, compositor fixo e perfil editável. Nenhum novo modelo, serviço pago
ou mudança no hardware foi introduzido. A personalidade é contexto textual, não
treinamento ou garantia de comportamento idêntico a uma personagem de ficção.

Os **65 testes passaram no Dell em 10,511 s**, incluindo os pesos reais preservados
e sete testes adicionais de perfil/conversas. Após o ajuste da especificação OpenAPI,
os **20 testes da API passaram em 1,650 s**. JavaScript passou `node --check`.
O backend de inferência nativo e o túnel de produção não foram reiniciados pela
atualização. Houve backup consistente e troca somente dos arquivos relacionados.

No navegador HTTPS foram testados login, perfil persistido, salvamento, criação de
duas conversas, renomeação e reabertura sem mistura de mensagens. Uma geração real
reconheceu o usuário a partir do perfil em 20,1 s. Em 390×700, o compositor terminou
na borda inferior do viewport, houve rolagem interna e nenhuma ultrapassagem horizontal;
o menu abriu/fechou e ficou inerte quando recolhido. A versão desktop também foi
conferida. O perfil permanece privado no runtime; testes usam dados fictícios.

API `/threads` requer autenticação, guarda grupos em metadados do esquema 2 e
exporta suas relações com mensagens. Perfil tem limites de tamanho e aceita limpeza
explícita. Exclusão de conversa remove somente seus dados; os testes de isolamento
e preservação de registros legados passaram. Não foram extraídos dados de outros
aplicativos para preencher o perfil. As pendências de voz, Access e avaliação ampla
do modelo descritas abaixo permanecem aplicáveis.

O ensaio HTTPS separado confirmou 401 sem credencial, isolamento, origem das
mensagens, exportação e OpenAPI. Após reiniciar somente API/túnel próprios, perfil e
conversas persistiram. O túnel respondeu 530 brevemente enquanto reconectava; após
a reconexão o ensaio completo passou. Apenas os IDs descartáveis criados pelo
verificador foram excluídos e a integridade final ficou `ok`. Novo login no navegador
restaurou conversas, títulos e perfil; logout removeu esses dados da página e revogou
a sessão de teste. Não houve erros JavaScript capturados.

### Estado mais recente: modelo moderno e interface revisada

Após a insatisfação com o GPT-2, o proprietário autorizou fazer o possível sem
serviços pagos e pediu a correção da interface. A instalação ativa passou para
Gemma 3 4B IT Q4_K_M via llama.cpp CPU no Dell. O código, licença e pesos OpenAI
permanecem preservados. Não houve treinamento nem melhoria dos pesos GPT-2.

Pesos e binários foram baixados diretamente no servidor e verificados com os
hashes fixados em [inferência](INFERENCE.md). A primeira carga de ensaio levou
4,572 s. As respostas reais passaram a ser inteligíveis em português. No navegador,
a apresentação com soma retornou `10 + 10 = 20` em 13,9 s; a explicação RAM/SSD
retornou duas frases coerentes em 14,8 s. São amostras funcionais, não um benchmark
abrangente de inteligência ou confiabilidade.

Os **58 testes passaram em 9,510 s no destino**, sem ignorados, incluindo cinco
ensaios reais GPT-2 para preservar compatibilidade e seis testes do novo adaptador,
contexto, UTF-8, cancelamento e persistência de origem das mensagens. Não houve
inferência do novo modelo no computador cliente. O cliente apenas transporta JSON.

O verificador HTTPS passou autenticação/401, origem/403, papéis, revogação, memória
editável, tarefas, comandos explícitos, duas gerações sequenciais e duas simultâneas
pela fila serial, integridade, backup, exportação e OpenAPI. Duas respostas sequenciais
levaram 9,589 e 11,052 s; as chamadas em paralelo terminaram em 8,504 e 10,043 s.
O total API+modelo ficou em cerca de 4,2 GiB de RAM, com cerca de 6,8 GiB disponíveis.
A CPU agregada observada variou com a janela de medição; durante o ensaio HTTPS,
a amostra foi 15,44% normalizada pelos quatro processadores lógicos. Disco livre
aproximadamente 78,6 GiB. Não são limites máximos garantidos.

Os três serviços próprios foram parados e iniciados em ordem controlada. Voltaram
como LocalService e a saúde autenticada passou. O túnel de produção e os listeners
Team Bike comparados preservaram os PIDs. Nenhum reboot ou alteração de firewall
foi executado. Uma falha inicial de quoting do PowerShell 5.1 foi corrigida com
stdin para o Python; a espera explícita por `Stopped` corrigiu a corrida de reversão.
Após o reinício, histórico, memória corrigida e tarefa concluída continuaram presentes.
O verificador removeu apenas seus registros identificados e a integridade final
retornou `ok`. Os dois registros descartáveis criados pela interface também foram
removidos, preservando os dados do proprietário.

A interface foi revisada com a skill Sites, mantendo o host existente e o frontend
HTML/CSS/JS. Login/logout, envio real, fonte persistida após novo login, nova conversa,
criação/edição de memória, criação/conclusão de tarefa, navegação e ajustes foram
verificados. O teste móvel 390 px revelou crescimento excessivo da lista de mensagens;
a altura foi limitada e a rolagem interna corrigida. O compositor permaneceu visível,
sem overflow horizontal; navegação fixa inferior e versão desktop conferidas. Sem
erros JavaScript capturados. A sessão de teste foi revogada. Capturas e inventários
detalhados ficam na entrega privada, fora do repositório.

O proprietário voltou a pedir o site e o túnel exclusivo foi reativado no hostname
existente. **As seções seguintes são históricas**: o estado API-only já não é atual.
Cloudflare Access, áudio audível, Whisper, GPU, reboot, recuperação após falha forçada
e acesso por rede móvel independente continuam não validados. O serviço usa HTTPS
e autenticação própria obrigatória; nenhum endpoint permite shell. Não há cobrança
por mensagem nem API comercial, mas a execução consome recursos e energia do host.

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
