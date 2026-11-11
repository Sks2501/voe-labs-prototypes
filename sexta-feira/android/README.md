# SEXTA-FEIRA Android 1.0.1

Cliente Android leve, universal, sem bibliotecas de publicidade/analytics ou motor
de inferência no telefone. O APK abre o frontend do servidor em um WebView protegido
e acrescenta síntese local e exportação pelo seletor de arquivos do Android.
O visual usa cores neutras, controles compactos e transparência discreta. O tema
acompanha o telefone por padrão, com opções claro/escuro; não incorpora código
Apple nem reproduz integralmente o app ou as capacidades do ChatGPT.

Requer Android 8.0/API26 ou posterior, WebView atualizado e Internet. A API própria
e o modelo continuam no Dell. O APK não inclui token. Autenticação usa o login da
aplicação e sessões de 12 horas; token fica na memória da página, sem persistência
nativa. Se o Android encerrar o processo, pode ser necessário entrar novamente.

## Compilar

Requer Python 3.11+, JDK17 e Android SDK oficial já instalado com plataforma 35 e
Build Tools 35.0.0. Não instala nem atualiza ferramentas globais, Gradle ou serviços.
Escolha um volume com pelo menos 512 MiB livres para temporários. Exemplo Windows:

```powershell
.\android\prepare-signing.ps1 -PrivateDirectory 'CAMINHO_PRIVADO' -JavaHome 'CAMINHO_JDK17'
.\android\build.ps1 -SdkRoot 'CAMINHO_SDK' -JavaHome 'CAMINHO_JDK17' -PrivateDirectory 'CAMINHO_PRIVADO' -OutputRoot 'VOLUME_COM_ESPACO\saida' -Python 'CAMINHO_PYTHON'
```

O primeiro script cria uma identidade RSA3072 de distribuição própria, com senha
aleatória protegida por DPAPI CurrentUser e ACL limitada ao usuário/SYSTEM. Preserve
a identidade e faça backup privado autorizado: atualizações precisam da mesma chave.
Não publique a chave, arquivo DPAPI ou senha. Uma identidade parcial existente não
é substituída. A senha chega ao assinador apenas pelo ambiente transitório do processo.

O build usa aapt2, javac, D8, zipalign e apksigner. Executa 14 verificações da política
de origem, verifica a assinatura e extrai os metadados do pacote. O recibo registra
versão, tamanho, hash e certificado público. Não substitui um APK existente diferente
no mesmo diretório: use um diretório de candidato e incremente a versão ao publicar
uma atualização. O projeto não contém binários do SDK ou dependências baixadas.

## Segurança e capacidades

- Somente permissão INTERNET; sem câmera, microfone, contatos ou armazenamento amplo.
- HTTPS obrigatório, certificado válido e host exato `sexta.teambike.online`. Sem
  arquivos/content URIs dentro do WebView, mixed content, terceiros ou depuração.
- O bridge `SextaAndroid` tem somente voz local, parar voz e solicitar exportação JSON.
  Não expõe tokens, shell, rede arbitrária ou leitura de arquivos. Conteúdo de terceiros
  é bloqueado; o servidor aplica CSP que impede frames e renderiza conversas como texto.
- TTS escolhe voz portuguesa com `isNetworkConnectionRequired=false`. Sem voz local
  instalada, o recurso fica indisponível; não troca por síntese em nuvem.
- Exportação tem limite de 5 MiB, valida o esquema e exige que o usuário escolha
  o destino no seletor Android. Nenhuma gravação arbitrária de caminhos é aceita.
- Teclado/insets, orientação, retorno ao chat/menu, parada da voz em segundo plano,
  tela de falha/retry e encerramento do WebView são tratados explicitamente.

## Distribuição

O proprietário autorizou download direto no hostname existente. `/android` mostra
a versão e o hash; `/downloads/sexta-feira-android.apk` entrega somente o arquivo
validado pelo recibo, e `/android/release.json` expõe apenas metadados públicos.
O runtime lê esses dois arquivos de `data/android-release/`. Não há rota de arquivos
genérica. A API continua autenticada; baixar o instalador não dá acesso a dados.

O APK é de distribuição direta e não está na Play Store. O Android pode exigir
permissão de instalação para o navegador usado no download. Isso é feito pelo
proprietário no telefone. Não foi instalado remotamente em aparelho físico.

## Validação e limites

Compilação, assinatura v2/v3, alinhamento, manifesto e política de origem foram
verificados. A suíte HTTP testa download GET/HEAD, integridade, caminho fixo, metadados
e manutenção da autenticação privada. O frontend e Liquid Glass são conferidos em
navegador responsivo. Instalação física, teclado Android real, TTS audível, seletor
Android e ciclo de vida em aparelho permanecem dependentes de teste no dispositivo;
não são declarados aprovados por uma compilação bem-sucedida.

Referências: [WebView](https://developer.android.com/develop/ui/views/layout/webapps/webview),
[segurança WebView](https://developer.android.com/privacy-and-security/risks/cross-app-scripting),
[apksigner](https://developer.android.com/tools/apksigner),
[voz local](https://developer.android.com/reference/android/speech/tts/Voice#isNetworkConnectionRequired()).

## Revisão visual 1.0.1

Fundo neutro, controles compactos em cápsulas, compositor de uma linha, ícones SVG
e menus em folhas modais. Respostas suportam formatação básica e blocos de código
por DOM, sem inserir HTML do modelo. Fontes permanecem nos detalhes da resposta.
O build obtém versão/code diretamente do manifesto.

A ponte nativa informa o modo claro/escuro do sistema e aplica a seleção às barras
do Android. Mudanças de tema não recarregam a página nem encerram a sessão. A versão
usa a mesma assinatura da 1.0.0 para instalação como atualização. O frontend também
é compatível com o APK anterior; a sincronização das barras depende da 1.0.1.
