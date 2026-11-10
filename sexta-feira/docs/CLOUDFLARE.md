# Cloudflare: roteiro de publicação privada

Nenhuma rota é configurada automaticamente pelos scripts. A aplicação permanece em `127.0.0.1:8765` (ou na porta livre escolhida). O hostname pretendido é `sexta.teambike.online`, com API `/api/v1`. Este documento não comprova que DNS, Access, Tunnel ou HTTPS tenham sido configurados.

Antes de publicar:

1. Inventarie o serviço Cloudflare Tunnel e suas rotas atuais, sem expor tokens ou credenciais. Preserve uma cópia privada da configuração. Descubra se as rotas são locais em YAML ou gerenciadas remotamente no painel.
2. Verifique API autenticada, origem autorizada, limite de requisição, login/sessões e interface em loopback. Adicione `"public_origin": "https://sexta.teambike.online"` ao `config.json` privado do runtime. `start.ps1` e o runner do serviço leem essa opção sem alterar variáveis globais. A API só aceita essa origem HTTPS exata, além do loopback.
3. Crie uma aplicação Cloudflare Access para o hostname exato, com política de permissão apenas ao proprietário, autenticação forte e sessão limitada. Não use política `Bypass` pública.
4. Adicione uma rota exclusiva `sexta.teambike.online` → `http://127.0.0.1:8765`, preservando a ordem e todas as outras rotas. Se for YAML, a entrada precisa ficar antes do catch-all final; não substitua o arquivo inteiro. Valide com o comando suportado pela versão instalada e faça somente o reload/reinício estritamente necessário do Tunnel, com autorização quando isso afetar a produção.
5. Teste por uma rede externa: HTTPS válido, solicitação de autenticação Access para visitante não autenticado, bloqueio de usuário não permitido, autenticação própria exigida depois do Access, rejeição de origem indevida e sucesso de conversa local. Confira a produção da Team Bike antes/depois.

O Access complementa a autenticação da SEXTA-FEIRA; não a substitui. Não exponha a porta da aplicação no firewall e não publique métricas administrativas sem autenticação. Não configure um endpoint sem proteção para contornar falhas no Access. Se qualquer verificação falhar, remova apenas a nova rota e mantenha a aplicação local, preservando as demais rotas.

O fluxo de interface usa token Bearer em memória, sem cookies de autenticação da aplicação. Isso evita credenciais anexadas automaticamente pelo navegador; a API ainda valida origem e host. Cookies do próprio Cloudflare Access são responsabilidade da configuração do Access.
