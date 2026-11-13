# Pesquisa pessoal na web

O modo automático reconhece perguntas públicas que dependem de informações recentes e consulta fontes. Você pode escolher pesquisa ligada ou desligada no chat. Pedidos explícitos como “pesquise notícias sobre ciclismo” e “leia este site: https://sqlite.org/” também funcionam. Digitar uma barra no início da mensagem abre os atalhos disponíveis.

O leitor de RSS exibe resultados públicos do Bing para uso pessoal e não comercial de um único proprietário. O feed fornece títulos e links; suas descrições não entram no modelo. As páginas das editoras são buscadas separadamente, respeitando robots.txt, e somente seus trechos lidos podem fundamentar uma síntese local. A fonte é marcada como **Página lida** ou **página não lida**. Não publique esta funcionalidade como um buscador para terceiros nem reutilize o feed comercialmente. [Referência oficial do RSS](https://blogs.bing.com/search/2005/1/RSS-Feeds-for-Search-Results/).

O protótipo DuckDuckGo HTML foi testado, mas recusou acesso automático no servidor na validação de 13/11/2026. Não foram contornados bloqueios, autenticação ou CAPTCHA. A disponibilidade e o ranking do RSS gratuito também podem mudar; isso não é uma API contratada nem possui garantia de cobertura ou atualidade.

## Qualidade e limites

O motor lê até três páginas de domínios distintos e usa até dois trechos na síntese. Cada afirmação deve conter uma referência `[1]`/`[2]`; URLs são acrescentadas pelo software a partir das fontes efetivamente consultadas. Links inventados, ausência de citações e citações longas geram uma resposta com fontes, em vez de uma síntese. Esses controles não provam a correção de cada afirmação. Fontes podem divergir e o modelo local pode errar.

Não há treinamento novo, aumento de capacidade dos pesos ou equivalência a um modelo de fronteira. A melhoria é a recuperação de evidências externas e sua apresentação explícita. Para documentação técnica, prefira pesquisas com o domínio oficial, por exemplo `site:docs.python.org sqlite3 backup`. Verifique datas e confirme assuntos importantes na fonte original.

Sem leitura de sites com login, paywall ou CAPTCHA, sem execução de JavaScript e sem leitura de PDF nesta versão. Uma página bloqueada não é apresentada como lida. Se a síntese local não ficar disponível, os links e trechos permitidos continuam visíveis. O histórico conserva a resposta e seus links, sem salvar páginas completas como memória pessoal.

## Privacidade e rede

Somente a consulta atual autorizada vai ao provedor de busca; histórico, perfil, memórias, token da API e credenciais do modelo não acompanham as requisições. Os sites externos recebem o IP do servidor. Identificadores pessoais evidentes e credenciais são recusados na pesquisa. Essa detecção é uma proteção adicional: não envie dados privados a buscadores públicos.

O cliente aceita apenas HTTPS público com certificado válido, porta 443 e sem credenciais na URL. Resolve DNS, rejeita endereços privados/reservados e fixa o IP público da conexão preservando a validação TLS do nome. Cada redirecionamento é revalidado. Não usa cookies, proxies de ambiente, cabeçalhos Authorization nem Referer nas consultas externas. Conteúdo de páginas é dado não confiável e nunca executa ferramentas ou comandos.

Limites iniciais: uma pesquisa em andamento, intervalo mínimo de 10 s, leitura de até 512 KiB por página, três redirecionamentos, janela de rede de aproximadamente 22 s e síntese local de até 75 s pela fila já existente. Cache de no máximo 16 pesquisas por cinco minutos, somente na RAM; a data original da coleta permanece visível. Não há processo permanente de navegador ou outro modelo carregado.

## API e cliente Android

Bearer obrigatório: `POST /api/v1/research` com **apenas** `{"query":"assunto"}` ou `{"url":"https://site/"}`. Também via ferramenta `web_research`, ou `POST /api/v1/conversations` com `{"message":"assunto","research":true}`. Ferramentas locais como `/hora` e `/hardware` têm prioridade e não enviam dados à internet.

A resposta informa `generated`, `source`, `tool`, `cached` e `research.sources` com URLs e estado da leitura. `generated:true` significa texto do modelo local, não confirmação factual. HTTP 429 limita concorrência/taxa; 503 indica falta de acesso às fontes; nenhuma resposta inventada substitui uma busca que falhou. O serviço continua em loopback, atrás do túnel próprio existente.

Android 1.0.2 abre uma fonte HTTPS no navegador externo somente após um toque explícito no link. As páginas externas nunca entram no WebView autenticado nem recebem o bridge nativo ou o token da assistente. O APK 1.0.1 pode mostrar os links, mas os bloqueia ao tentar abri-los; atualize o cliente para esse recurso. A instalação no aparelho físico precisa ser validada pelo proprietário.
