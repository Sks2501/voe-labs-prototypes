# Cloudflare: roteiro de publicação privada

A aplicação escuta em `127.0.0.1:8765` (ou na porta livre escolhida). O hostname pretendido é `sexta.teambike.online`, com API `/api/v1`. O provisionamento local não publica uma rota. O script separado `publish-private-tunnel.ps1` permite uma publicação expressamente autorizada, com túnel e serviço próprios, sem reiniciar o túnel de produção. Este roteiro não é evidência de um teste de conectividade.

Antes de publicar:

Estado verificado em 11/11/2026: o proprietário reautorizou o site no hostname
existente; `SextaFeiraTunnel` está ativo. HTTPS, autenticação, origem e conversa real
passaram nos testes mais recentes. O `Cloudflared` da produção não foi reiniciado.
Cloudflare Access não foi configurado. Consulte [validação](VALIDATION.md).

1. Inventarie o serviço Cloudflare Tunnel e suas rotas atuais, sem expor tokens ou credenciais. Preserve uma cópia privada da configuração. Descubra se as rotas são locais em YAML ou gerenciadas remotamente no painel.
2. Verifique API autenticada, origem autorizada, limite de requisição, login/sessões e interface em loopback. Adicione `"public_origin": "https://sexta.teambike.online"` ao `config.json` privado do runtime. `start.ps1` e o runner do serviço leem essa opção sem alterar variáveis globais. A API só aceita essa origem HTTPS exata, além do loopback.
3. Avalie Cloudflare Access como proteção adicional para o hostname exato, com política de permissão apenas ao proprietário, autenticação forte e sessão limitada. Não use política `Bypass` pública. Se não houver credencial administrativa adequada para configurar Access, registre a pendência: a autenticação própria por Bearer de alta entropia e sessões expirantes continua obrigatória para todos os endpoints da API. A página de login e os arquivos estáticos não contêm dados pessoais. Não declare Access ativo sem testá-lo.
4. Adicione uma rota exclusiva `sexta.teambike.online` → `http://127.0.0.1:8765`, preservando a ordem e todas as outras rotas. Se for YAML, a entrada precisa ficar antes do catch-all final; não substitua o arquivo inteiro. Valide com o comando suportado pela versão instalada e faça somente o reload/reinício estritamente necessário do Tunnel, com autorização quando isso afetar a produção.
5. Teste pelo hostname HTTPS: certificado válido, bloqueio de API sem credencial, sessão revogável, rejeição de origem indevida e inferência local real. Quando Access estiver configurado, teste também o desafio e o bloqueio de usuários não permitidos. Registre de onde o teste foi feito; teste pelo hostname público a partir da mesma rede não comprova uma rede externa independente. Confira a produção da Team Bike antes/depois.

O Access complementa a autenticação da SEXTA-FEIRA; não a substitui. Não exponha a porta da aplicação no firewall e não publique métricas administrativas sem autenticação. Não configure um endpoint sem proteção para contornar falhas no Access. Se qualquer verificação falhar, remova apenas a nova rota e mantenha a aplicação local, preservando as demais rotas.

O fluxo de interface usa token Bearer em memória, sem cookies de autenticação da aplicação. Isso evita credenciais anexadas automaticamente pelo navegador; a API ainda valida origem e host. Cookies do próprio Cloudflare Access são responsabilidade da configuração do Access.

Para uma instância exclusiva, execute o script separado com `-RuntimeRoot`, `-CloudflaredPath` e `-OriginCertificate` apontando para arquivos locais autorizados. Ele usa a instalação existente somente como origem de uma cópia verificada do executável e como credencial administrativa para criar o novo túnel/DNS. O serviço `SextaFeiraTunnel`, executado como LocalService, recebe somente sua credencial específica de túnel. Não recebe o certificado administrativo da conta. O comando de DNS não usa `--overwrite-dns`. Nome de túnel, DNS ou artefatos existentes provocam interrupção para revisão, sem substituição. Logs têm rotação e as atualizações do executável são manuais.

Reversão: pare somente `SextaFeiraTunnel`; isso retira a aplicação da Internet sem afetar `Cloudflared`. Preserve o recibo privado e faça uma remoção administrativa explícita apenas do DNS/túnel criados para a SEXTA-FEIRA. O backup `cloudflare/app-config.before.json` permite restaurar a origem local; a SEXTA-FEIRA pode continuar funcionando em loopback.
