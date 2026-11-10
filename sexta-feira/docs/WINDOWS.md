# Windows: instalação isolada e operação

O diagnóstico vale somente para a máquina em que o script é executado. Antes de instalar no RDP, execute `scripts\audit.ps1` e examine o JSON privado. `HypervisorPresent` sozinho não comprova que o Windows é convidado de uma VM. A VRAM do `Win32_VideoController` é apenas indicativa; use `nvidia-smi` quando disponível. A GPU permanece desativada.

## Instalação

Ao executar `instalar_windows.bat` por duplo clique, a janela aguarda uma tecla
ao terminar para que o resultado permaneça visível, inclusive em caso de erro.
Para automação sem interação, use `scripts/install.ps1` diretamente ou defina
`SEXTA_NO_PAUSE=1` somente no processo que chama o BAT.

Use Python 3.11 a 3.13 de 64 bits em um local acessível à conta de serviço; prefira uma instalação por máquina, já aprovada pelo proprietário. O script não instala nem atualiza o Python global. A seleção automática procura primeiro `py -3.11`, depois `-3.12`, `-3.13` e, por fim, o `python` existente no PATH, sempre validando versão e arquitetura. A versão preferida é 3.11; `-Python` permite selecionar explicitamente outro interpretador suportado. É necessário ao menos 5 GB livres no volume de runtime e 1,8 GB de RAM livre no momento da instalação; esses mínimos não substituem a medição junto aos serviços de produção.

Em PowerShell, na pasta `sexta-feira`:

```powershell
.\scripts\audit.ps1
.\scripts\install.ps1 -Python 'C:\Python311\python.exe' -RuntimeRoot 'D:\SextaFeiraRuntime'
.\scripts\start.ps1 -RuntimeRoot 'D:\SextaFeiraRuntime'
```

Escolha uma pasta de runtime nova, exclusiva da SEXTA-FEIRA. O exemplo D: só se aplica se esse volume existir. Não execute a instalação no C: quando o volume não tiver espaço. O script recusa portas ocupadas e diretórios não identificados como runtime próprio. Não encerra processos existentes, não altera firewall, não configura Cloudflare e não reinicia o Windows. `-SkipWeights` permite preparar dependências e SQLite sem baixar pesos, mas deixa inferência e instalação do serviço pendentes.

A instalação usa ambiente virtual próprio, dependências controladas pelo repositório, armazenamento do modelo separado, SQLite próprio, testes automatizados e smoke de inferência real em um banco temporário. Não modifica conversas existentes durante o smoke. O relatório privado fica em `diagnostics\installation.json`; erros mantêm os arquivos para diagnóstico. Leia também os testes marcados como ignorados. Nenhuma saída do instalador deve ser interpretada como validação de serviço Windows ou acesso externo.

O token administrativo é criado uma única vez em `data\access.token`, sob ACL restritiva. Abra esse arquivo localmente em um editor autorizado, copie o token e feche o editor. Não copie tokens para comandos, documentos, logs, capturas ou GitHub. A interface troca o token por uma sessão e guarda a sessão somente na memória da página. Prefira entrar como usuário para uso diário. Recarregar a página remove o token da memória do navegador.

Para testar a API já iniciada:

```powershell
.\scripts\health.ps1 -RuntimeRoot 'D:\SextaFeiraRuntime'
```

## Serviço persistente

O mecanismo preparado é [WinSW 2.12.0](https://github.com/winsw/winsw/releases/tag/v2.12.0), executando o Python do ambiente virtual como `NT AUTHORITY\LocalService`. O binário não está incluído no Git. Forneça o executável x64 oficial e seu SHA256 validado por uma fonte confiável independente. O script exige checksum correspondente e versão 2.12.0; calcular um hash depois de baixar um executável não comprova, por si só, sua origem. Não use um valor de exemplo como checksum.

Depois de validar o modelo e encerrar a execução em primeiro plano, em PowerShell elevado:

```powershell
.\scripts\service.ps1 -Action Install -RuntimeRoot 'D:\SextaFeiraRuntime' -WinSWPath 'D:\Downloads\WinSW-x64.exe' -WinSWSha256 'HASH_SHA256_REAL_VALIDADO'
.\scripts\service.ps1 -Action Start -RuntimeRoot 'D:\SextaFeiraRuntime'
.\scripts\service.ps1 -Action Status -RuntimeRoot 'D:\SextaFeiraRuntime'
.\scripts\health.ps1 -RuntimeRoot 'D:\SextaFeiraRuntime'
```

`Install` registra apenas o serviço próprio e não o inicia. O instalador não substitui um serviço existente nem reutiliza um serviço de outro executável. A conta LocalService tem leitura no código e nos modelos e modificação apenas nos dados, logs e temporários próprios. O registro do serviço recusa ambientes virtuais cujo Python base fica em `AppData` ou em qualquer perfil de usuário. Essa instalação por usuário pode servir para testes em primeiro plano, mas não é aceita para LocalService. O proprietário precisa instalar um interpretador separado, por máquina, fora de perfis, e preparar um runtime novo com esse interpretador. O script não move o Python nem altera ACLs do interpretador ou de outros perfis. Confirme que o interpretador e suas DLLs são legíveis para LocalService. Não conceda direitos amplos a diretórios de outros projetos para corrigir falhas de acesso.

A configuração preparada utiliza inicialização automática atrasada, recuperação após 5 s e 30 s, depois nenhuma nova tentativa até intervenção ou reinício do contador após uma hora. O encerramento usa um evento nomeado Windows para `server.shutdown()` e encerramento do motor, com limite de 90 s do wrapper. Não existe endpoint administrativo público de shell. Logs do wrapper giram a 1 MB, mantendo três arquivos; logs de aplicação possuem política própria.

Valide no servidor de destino, sem parar os demais serviços: Start → health autenticado → inferência real → Stop → Start → health. Compare o inventário de serviços e portas antes/depois. A disponibilidade de toda a produção precisa de seus próprios testes autorizados. A presença dos scripts não significa que o serviço foi instalado ou testado.

## Atualização e reversão

1. Registre commit, versões de dependências, configuração privada e estado da produção. Faça backup consistente do SQLite pela função da aplicação; não copie somente o `.sqlite3` aberto com WAL.
2. Pare apenas `SextaFeira` com `service.ps1 -Action Stop`. Preserve dados, token, modelos e configuração.
3. Prepare a nova revisão e um ambiente virtual separado; execute testes e smoke com banco temporário antes de alterar o runtime ativo.
4. Atualize apenas a configuração/executável da SEXTA-FEIRA de forma controlada, inicie o serviço e valide API e inferência. Não misture atualização de código com atualização automática das dependências.
5. Se falhar, pare somente a SEXTA-FEIRA, retorne à revisão e ao ambiente virtual registrados e valide novamente. Restaure o backup do banco apenas se a alteração de esquema exigir e com autorização para substituir os dados.

`service.ps1 -Action Uninstall` requer o serviço parado e remove apenas seu registro. Não exclui runtime, backups, banco ou modelos. Não há limpeza automática de diretórios.

## Voz

A interface só seleciona vozes com `localService=true` em português. Se nenhuma estiver disponível, a leitura fica indisponível. O microfone permanece desativado: Whisper local ainda precisa de instalação e validação específicas. Não há reconhecimento via serviço externo como substituto silencioso.

## Migração de diretório de dados legado

`init` só protege e inicializa uma pasta vazia ou uma pasta já identificada pelo marcador `.sexta-data` da SEXTA-FEIRA. Se encontrar arquivos em uma pasta sem marcador válido, preserva conteúdo e permissões e recusa continuar. Não crie esse marcador manualmente em um diretório desconhecido, não o copie de outro projeto e não contorne a recusa alterando a validação.

Para uma instalação antiga:

1. Identifique o diretório exato e a versão antiga. Pare apenas a SEXTA-FEIRA, preserve o diretório inteiro e faça um backup SQLite consistente e privado; utilize a função de backup da versão antiga ou a API SQLite `Connection.backup`. Não copie somente o arquivo principal de um banco aberto em WAL.
2. Verifique a integridade do backup e preserve, separadamente, configurações e credenciais locais. Não envie o backup ao GitHub. Não apague nem renomeie o diretório antigo.
3. Escolha um runtime novo e exclusivo. Execute o instalador com esse destino ou `init` apontando `SEXTA_DATA_DIR` para uma pasta nova e vazia. O próprio `init` cria o marcador e as permissões; nenhum arquivo antigo deve ser copiado antes dessa inicialização.
4. Com a aplicação nova parada e o SQLite recém-criado ainda sem conversas, memórias ou tarefas, restaure o backup consistente para esse banco novo usando a API de backup do SQLite. Verifique o destino antes da restauração; não substitua um banco que já contenha dados de uso. Preserve o token novo gerado pelo `init` e revogue sessões restauradas da instalação anterior.
5. Abra o banco restaurado com a versão nova para aplicar somente migrações suportadas. Execute `init` novamente na pasta marcada para reaplicar ACLs também aos arquivos restaurados. Valide integridade, histórico, memórias e tarefas, além da autenticação com o token novo. Versões de esquema futuras são recusadas.
6. Mantenha o diretório antigo e o backup até concluir os testes e a decisão de migração. Se falhar, encerre apenas a instância nova e retorne à instalação antiga preservada. Uma restauração que substitua dados de uso existentes exige autorização específica.

A migração não é executada automaticamente pelos scripts. Os passos de restauração precisam ser adaptados aos caminhos e à versão realmente encontrados no servidor, com verificação do destino antes de gravar.
