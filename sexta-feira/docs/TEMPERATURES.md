# Temperaturas e recursos do servidor

`/hardware`, `/cpu`, `/ram`, `/recursos` ou `/status` retornam CPU, RAM, disco e temperaturas em uma resposta determinística. Pedidos diretos como “Como está o servidor?” usam a mesma ferramenta. `GET /api/v1/hardware` exige Bearer e oferece uma lista limitada de métricas ao proprietário em sessão user. O endpoint administrativo `/metrics` continua restrito. Não retorna PIDs, portas, processos de outros projetos, caminhos, tokens ou inventário de rede.

O painel mostra modelo da CPU, processadores lógicos, uso total de CPU, RAM total/usada/disponível, RAM da IA/API e disco total/usado/livre. Atualiza a cada 10 s somente quando visível e autenticado, sem sobrepor requisições. Uso de CPU é calculado entre amostras `GetSystemTimes` (kernel inclui idle); a primeira amostra não inventa 0%. A RAM vem de `GlobalMemoryStatusEx`; disco é o volume de dados da aplicação. Unidades de capacidade: GiB, diferentes de °C.

`/temperaturas`, `/temperatura` ou `/sensores` consultam medidas reais **do servidor da API**, inclusive no Android. Perguntas curtas como “Qual é a temperatura da VPS?” usam a mesma ferramenta determinística. A saída do modelo nunca é interpretada como chamada de ferramenta.

O botão **+ → Temperaturas** faz a consulta no chat. **Mais → Modelo e desempenho → Atualizar** mostra os sensores e a data da coleta. Não requer nova instalação do APK: a interface vem da API.

## Fontes e limites

- `Get-StorageReliabilityCounter`: temperatura atual dos discos que oferecem o contador, em °C. Zero, nulo e máximos não suportados não viram leituras.
- `MSAcpi_ThermalZoneTemperature`: zona térmica genérica, convertida de décimos de kelvin para °C: `valor / 10 - 273,15`. **Não é identificada como temperatura interna do processador.** O firmware pode fornecer valores pouco representativos ou constantes.
- CPU: provedor opcional LibreHardwareMonitor 0.9.6 + PawnIO 2.2.0, ativado somente após autorização específica do driver. Pacote e núcleos são identificados separadamente. Sem provedor ativo, aparece indisponível.
- GPU, RAM, placa-mãe e bateria: temperatura não implementada; uso/capacidade de RAM continua disponível. Não afirma que os componentes estão frios, normais ou seguros.

Em uma VM, os sensores físicos podem estar ausentes. Nenhuma medição é estimada. A coleta por minuto não detecta todos os picos e não substitui proteção térmica do hardware.

Fontes primárias: [Windows Storage](https://learn.microsoft.com/en-us/powershell/module/storage/get-storagereliabilitycounter), [ACPI e zonas térmicas](https://learn.microsoft.com/en-us/windows-hardware/design/device-experiences/design-guide), [GetSystemTimes](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getsystemtimes). O coletor Windows básico não instala drivers. O provedor CPU tem instalação opcional separada; não utiliza WinRing0 nem altera políticas de segurança.

## Provedor opcional de temperatura CPU

Na implantação de 11/11/2026, o proprietário autorizou a instalação. PawnIO 2.2.0 foi instalado com código zero, sem reinicialização, e o coletor passou a fornecer CPU pacote e dois núcleos. API autenticada, painel e disparos automáticos foram verificados. O sensor ACPI continua separado. O procedimento abaixo descreve preparação/ativação em um runtime identificado; não é necessário reinstalar para usar os sensores já ativos.

`cpu-sensors.ps1 -RuntimeRoot ... -Action Prepare` baixa e verifica os artefatos oficiais, prepara uma pasta com escrita somente para SYSTEM/Administradores e inspeciona metadados da biblioteca. **Não executa o instalador nem abre hardware.**

- [LibreHardwareMonitor 0.9.6](https://github.com/LibreHardwareMonitor/LibreHardwareMonitor/releases/tag/v0.9.6): SHA-256 do ZIP .NET Framework `086d9f1b5a99e643edc2cfaaac16051685b551e4c5ac0b32a57c58c0e529c001`.
- [PawnIO 2.2.0 oficial](https://github.com/namazso/PawnIO.Setup/releases/tag/2.2.0): SHA-256 `1f519a22e47187f70a1379a48ca604981c4fcf694f4e65b734aaa74a9fba3032`; Authenticode válido, emissor do executável `namazso.eu`.

Somente após autorização do proprietário: `cpu-sensors.ps1 -RuntimeRoot ... -Action Activate -AllowKernelDriver`. Instala edição oficial assinada via `-install -silent`; não habilita edição unrestricted, acesso para usuários comuns ou desativa proteções. Código 3010 interrompe a ativação sem reiniciar o servidor. Driver preexistente sem recibo próprio não é substituído.

O coletor SYSTEM verifica o hash das DLLs, abre apenas o grupo CPU, lê temperatura do pacote/núcleos e fecha os recursos em `finally`. Grupos de controladores, placa-mãe, SPD de memória, GPU e ventoinhas ficam desativados. A API LocalService só lê o JSON, sem acesso ao driver. A preparação e o script não significam que houve leitura real: a ativação e o teste no hardware devem ser registrados no recibo privado.

Para desabilitar somente a integração: `cpu-sensors.ps1 -RuntimeRoot ... -Action Disable`. O driver permanece preservado; sua remoção é operação administrativa separada e deve verificar se outro aplicativo o utiliza. Não há atualização automática dos binários.

## Instalação isolada no Windows

Depois de validar o runtime e os testes, em PowerShell administrativo:

```powershell
.\scripts\temperature-service.ps1 -RuntimeRoot C:\SextaFeiraRuntime -Action Install
.\scripts\temperature-service.ps1 -RuntimeRoot C:\SextaFeiraRuntime -Action Status
```

A tarefa própria `\SextaFeira\SextaFeiraTemperatures` roda como SYSTEM para ler os provedores Windows sem elevar a API LocalService. Executa somente o script fixo copiado para `runtime\sensors`, protegido contra gravação pela API e por usuários comuns. Não recebe argumentos do chat, não acessa rede, não controla ventoinhas e não instala drivers. O instalador recusa runtime sem identidade, tarefa com ação diferente, diretório de outro sistema e permissões de escrita inseguras no pai.

Coleta na inicialização e a cada 60 s; prioridade abaixo do normal, sem sobreposição, duração máxima de 30 s. Não há ciclo de reinicialização. Publica JSON pequeno por substituição atômica. A API somente lê até 64 KiB, valida valores finitos, fontes permitidas e horário. Mais de 180 s: `stale`, sem números antigos apresentados como atuais. Falha/ausência: `unavailable`.

`scripts/service_runner.py` seleciona o snapshot do mesmo runtime da configuração privada. Em execução manual, configure `SEXTA_TEMPERATURE_FILE` com o caminho privado do snapshot. O cliente não pode escolher caminhos. Credenciais, números de série e inventário privado não são incluídos.

API Bearer obrigatória: `GET /api/v1/temperatures` ou `POST /api/v1/tools` com `{"name":"server_temperatures","parameters":{}}`. Papel user pode ler sensores; métricas administrativas continuam restritas. Retorno contém `scope: server`, estado, horário UTC, idade, intervalo, leituras em °C com fonte e componentes indisponíveis. Dados indisponíveis retornam HTTP 200 com estado explícito; não são erros de autenticação.

## Manutenção e reversão

Para pausar apenas o coletor: `temperature-service.ps1 -RuntimeRoot ... -Action Disable`. A API passa a informar coleta desatualizada em até 180 s. Dados e serviços de outros projetos não são alterados. Para atualização, aguarde a tarefa terminar, preserve os arquivos próprios e execute Install novamente (idempotente, sem apagar diretórios). O script copiado deve acompanhar a versão revisada do código; não conceda escrita ao LocalService.

Reversão da interface/API: restaure somente os arquivos da versão anterior a partir do backup da atualização e reinicie apenas o serviço SextaFeira. Não restaure o banco sobre conversas novas. Desative a tarefa; mantenha os arquivos até revisão. A ativação de novos sensores ou drivers é uma alteração separada.
