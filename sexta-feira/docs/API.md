# API privada v1

Pesquisa pessoal: `POST /api/v1/research` com apenas `query` (2–320 caracteres) ou `url` (HTTPS público), autenticado. A ferramenta `web_research` aceita os mesmos parâmetros; no chat use `/pesquisar assunto`, `/site URL` ou `research:true`. Fontes e data acompanham o resultado; o modelo de síntese permanece local. Veja [WEB_RESEARCH.md](WEB_RESEARCH.md) para escopo pessoal do RSS, limites e privacidade.

A aplicação atende **um único proprietário**. Sessões de usuário e administrador
compartilham os dados pessoais desse proprietário; não é um serviço multitenant.
O processo escuta em `127.0.0.1:8765`. Publicação requer HTTPS e controle de acesso
externo conforme [CLOUDFLARE.md](CLOUDFLARE.md).

Todas as rotas `/api/v1`, inclusive saúde e OpenAPI, exigem
`Authorization: Bearer <credencial>`. Nunca coloque a credencial na URL. O token
da instalação vem de um arquivo privado criado por `python -m sexta_feira init`.
O servidor não imprime o segredo. A interface de login e seus arquivos estáticos
podem ser carregados sem autenticação; não contêm dados pessoais.

Por solicitação do proprietário, o instalador também é público fora de `/api/v1`:
`GET /android` (instruções), `GET /android/release.json` (metadados públicos) e
`GET`/`HEAD /downloads/sexta-feira-android.apk` (APK verificado). O serviço aceita
somente o nome de release previsto, até 10 MiB, tamanho e SHA-256 correspondentes.
Não há download de caminhos arbitrários. A disponibilidade do instalador não
concede sessão ou acesso à API. Veja [Android](../android/README.md).

`POST /api/v1/sessions` recebe `{ "role": "user" }` ou `admin`, autenticado por uma
credencial válida. A resposta contém um novo `token`, `id`, `role` e `expires_at`
(timestamp Unix). O token é mostrado somente nesta resposta e o SQLite guarda seu
SHA-256. Sessões expiram em 12 horas e o limite é 100 sessões simultâneas. Um
usuário não pode criar uma sessão administrativa. A interface guarda a sessão
somente na memória da página; fechar/recarregar a página perde a credencial local.
O botão Sair também revoga a sessão no servidor.

Não há cookies de autenticação. Cada chamada depende do cabeçalho Bearer, sem
credenciais ambiente que possam ser enviadas por um formulário CSRF. Origens e
hosts são validados e a API não libera CORS. Para um túnel, configure uma única
`SEXTA_PUBLIC_ORIGIN` HTTPS exata. Cabeçalhos encaminhados não concedem privilégios.

| Rota depois de `/api/v1` | Métodos | Uso |
| --- | --- | --- |
| `/health` | GET | Disponibilidade autenticada, sem diagnóstico administrativo |
| `/state` | GET | Histórico recente, memórias, tarefas, preferências e estado do modelo |
| `/model` | GET | Estado real do motor; não força carregamento dos pesos |
| `/conversations` | POST | `{ "message": "texto", "context_after": 123 }`; modelo local ou comando explícito; corte opcional |
| `/history` | GET, DELETE | Página de histórico ou exclusão do histórico |
| `/threads` | GET, POST | Conversas do proprietário; criação com título opcional de até 80 caracteres |
| `/threads/{id}` | GET, PATCH, DELETE | Mensagens paginadas, renomear com `title` ou excluir somente a conversa |
| `/memories` | GET, POST | Página de memórias; criação com `{ "content": "texto" }` |
| `/memories/{id}` | PATCH, DELETE | Correção com `content` ou exclusão |
| `/tasks` | GET, POST | Página de tarefas; criação com `content` |
| `/tasks/{id}` | PATCH, DELETE | Atualizar `content`/`completed` booleano ou excluir |
| `/preferences` | GET, PATCH | `voice_enabled`, `voice_rate` entre 0.5 e 2, `language: pt-BR` |
| `/sessions` | POST | Criar sessão com privilégio igual ou inferior ao atual |
| `/sessions` | GET | Administrador: inventário sem tokens ou hashes |
| `/sessions/current` | DELETE | Revogar a sessão atual; não revoga token da instalação |
| `/sessions/{id}` | DELETE | Administrador: revogar uma sessão |
| `/tools` | POST | Ferramenta explícita com `name` e objeto `parameters` |
| `/metrics` | GET | Administrador: CPU, RAM, disco, requisições e fila |
| `/export` | GET | Exportação JSON de dados pessoais, sem sessões/credenciais |
| `/admin/integrity` | GET | Administrador: `PRAGMA integrity_check` |
| `/admin/backup` | POST | Administrador: corpo `{}`; backup SQLite consistente |
| `/openapi.json` | GET | Especificação OpenAPI 3.1 autocontida |

As páginas de histórico/memórias/tarefas aceitam `limit` e `before` (ID exclusivo).
O máximo é 100 mensagens, 100 memórias ou 200 tarefas por página. Para buscar uma
página anterior, envie `before` igual ao menor ID da página atual. Histórico vem
em ordem cronológica dentro da página; memórias/tarefas vêm em ID decrescente.
Memórias/tarefas retornam também `total`. `/state` informa `counts` e `limits`.

Novas memórias têm limite de 100 registros; tarefas têm limite de 200, incluindo
as concluídas. A API responde 409 ao atingir o limite, sem substituir registros.
Dados legados acima desses limites são preservados e continuam consultáveis por
paginação, corrigíveis, exportáveis e excluíveis.

## Comandos explícitos no chat

Somente mensagens do usuário com estes prefixos acionam ferramentas:

| Comando | Ferramenta | Efeito |
| --- | --- | --- |
| `/hora` | `system_time` | Hora e fuso do servidor |
| `/tarefas` | `list_tasks` | Consulta tarefas |
| `/memorias` | `list_memories` | Consulta memórias explicitamente salvas |
| `/tarefa texto` | `create_task` | Cria a tarefa informada |
| `/lembrar texto` | `save_memory` | Salva a memória informada |

A resposta traz `source: tool`, `generated: false` e `action_executed: true` depois
da execução real. Listas no chat mostram até dez registros; use a lista da interface
para consultar os demais. Conversas normais trazem `source: local_model` no backend
llama.cpp (`gpt2` no backend histórico), `generated: true`, `model` e
`action_executed: false`. Nenhum texto produzido pelo modelo volta a ser analisado
como comando. A fonte e o nome do modelo são persistidos atomicamente com o par de
mensagens em metadados SQLite, incluídos no histórico e exportação. Registros antigos
sem origem permanecem sem atribuição inventada. O esquema continua versão 2.

O campo opcional `context_after` aceita um ID inteiro positivo e restringe somente
o histórico enviado ao modelo. Não apaga dados. É compatibilidade para clientes
anteriores; a interface atual usa `thread_id`. O corte configurado na troca do
backend mantém o histórico GPT-2 acessível em Ajustes, fora do contexto padrão.
Não há agendador de notificações nem execução de shell.

A interface atual cria conversas com `POST /threads` e envia `thread_id` (32 dígitos
hexadecimais minúsculos) junto de `message` para `/conversations`. A resposta também
informa esse ID. Somente o histórico dessa conversa entra no modelo. O endpoint
legado sem ID continua aceito. Até 100 conversas; `GET /threads/{id}` aceita
`limit` até 100 e `before`, assim como histórico. Sessões autorizadas compartilham
o espaço do mesmo proprietário. Excluir conversa não exclui memórias ou tarefas.

`PATCH /preferences` também aceita `preferred_name` (80 caracteres), `about_me`
(480), `goals` (400), `response_style` (160). São textos explicitamente fornecidos,
inclusive vazios para limpar; dados entram no contexto do backend Gemma e na
exportação. Veja [personalização](CONVERSATIONS.md).

## Limites e proteção dos dados

- Corpo JSON até 8192 bytes; mensagem até 1600 caracteres; memórias/tarefas até 480.
- 60 requisições por minuto por IP de conexão e até 16 conexões HTTP em atendimento.
  Um túnel pode fazer os clientes compartilharem o mesmo IP local e esse limite.
- A inferência tem sua própria fila pequena e somente um trabalhador de CPU.
- Exportação: uma por vez; estimativa conservadora máxima de 5 MiB de JSON e
  10.000 registros por tabela, validada antes de materializar dados. O snapshot
  SQLite mantém a exportação consistente. Arquivos maiores exigem backup admin.
- Backups: uma criação por vez, máximo de dez arquivos e reserva mínima de 64 MiB
  além do espaço estimado necessário. Nenhum backup antigo é apagado automaticamente.
- Exclusão de histórico/memórias/tarefas é uma operação lógica no banco corrente.
  Backups anteriores ainda podem conter dados excluídos; gerencie sua retenção.
- Logs têm rotação de 1 MiB e três cópias, sem URLs, tokens ou conteúdo das conversas.
- SQLite não é criptografado pela aplicação: a proteção depende das ACLs privadas
  e do armazenamento/backup do Windows. Esquemas mais novos são recusados antes
  de qualquer migração; a versão atual do esquema é 2.

Erros têm `{ "error": "mensagem", "code": "identificador" }`. Principais status:
400 validação, 401 autenticação, 403 privilégio/origem, 404 inexistente, 409 limite
de dados, 413 corpo/exportação excessivo, 415 tipo de conteúdo, 421 host inválido,
429 frequência/fila/exportação ocupada, 503 indisponibilidade e 504 timeout de
inferência. Erros internos não devolvem caminhos, detalhes de exceções ou segredos.

## Temperaturas

`GET /api/v1/hardware` exige Bearer (user ou admin) e mostra CPU total, RAM, disco, RAM da IA e temperaturas ao proprietário. Ferramenta `server_hardware` não aceita parâmetros. Comandos `/hardware`, `/cpu`, `/ram`, `/recursos` e `/status`; pedidos diretos sobre o estado do servidor também usam a ferramenta. Métricas administrativas continuam em `/metrics`, exclusivo de admin. Recursos não incluem caminhos, credenciais ou PIDs. CPU percentual é média entre amostras e não é temperatura.

`GET /api/v1/temperatures` exige Bearer (user ou admin). Também disponível em `POST /api/v1/tools` como `server_temperatures`, sem parâmetros, e no chat por `/temperaturas`. São leituras do servidor, com origem, data, idade e componentes indisponíveis. Dados com mais de 180 s não retornam temperaturas atuais. Veja [TEMPERATURES.md](TEMPERATURES.md) para instalação isolada e limites dos sensores.
