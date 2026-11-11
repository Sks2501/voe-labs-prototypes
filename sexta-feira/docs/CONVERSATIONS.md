# Conversas e personalização

A interface foi reorganizada com o padrão de um chat: lateral de conversas salvas,
conteúdo central e compositor fixo. No celular, o menu abre como gaveta. A identidade
continua SEXTA-FEIRA; a aplicação não é uma interface oficial do ChatGPT.

Cada conversa tem ID aleatório, título, datas e mensagens próprias. Nova conversa
começa vazia; sua criação ocorre no primeiro envio. Abrir outra conversa altera
somente o contexto daquela conversa, sem misturar os demais assuntos. Renomear e
excluir estão disponíveis; a exclusão pede confirmação e exige backup para recuperar.
Até 100 conversas; até 100 mensagens por página, com exibição progressiva limitada
a 500 no navegador. A inferência usa somente as últimas mensagens pertinentes,
respeitando o corte de contexto do motor. O histórico anterior continua acessível.

O SQLite mantém o esquema 2: a tabela metadata existente guarda os descritores
`conversation:<id>` e vínculos `message-thread:<id da mensagem>`. A gravação do par
usuário/resposta, fontes, vínculos e data da conversa ocorre na mesma transação.
Excluir uma conversa remove somente seus vínculos/mensagens/fontes; histórico sem
conversa e outros registros são preservados. Backups existentes continuam válidos.
Exportações incluem `threads`, `thread_id` em mensagens e perfil em preferências.

Em **Sobre você**, o usuário edita explicitamente quatro campos: nome preferido,
informações pessoais, objetivos e estilo de resposta. Limites respectivos: 80, 480,
400 e 160 caracteres. Campos vazios removem esses dados do perfil. As informações
entram no contexto das conversas do backend Gemma, mesmo sem correspondência literal
de palavras. Conversas e perfil pertencem ao mesmo proprietário; os papéis não
oferecem isolamento entre pessoas diferentes.

O estilo configurado é inspirado na SEXTA-FEIRA de Tony Stark: calma, objetividade,
atenção e humor discreto. É configuração de contexto, sem fine-tuning, clonagem de
voz ou novas capacidades do modelo. A assistente não se apresenta como a personagem
real, não inventa dados pessoais e não executa instruções geradas. Ferramentas
continuam dependendo de comandos explícitos e da lista autorizada.

O usuário controla as informações salvas. Não são coletados dados de outros apps,
contatos ou conversas do Codex; histórico não é convertido em memória automaticamente.
Vozes locais, quando disponíveis, mantêm as limitações descritas nos Ajustes.
