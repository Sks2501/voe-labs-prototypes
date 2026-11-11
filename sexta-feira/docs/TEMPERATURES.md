# Temperaturas do servidor

`/temperaturas`, `/temperatura` ou `/sensores` consultam medidas reais **do servidor da API**, inclusive no Android. Perguntas curtas como “Qual é a temperatura da VPS?” usam a mesma ferramenta determinística. A saída do modelo nunca é interpretada como chamada de ferramenta.

O botão **+ → Temperaturas** faz a consulta no chat. **Mais → Modelo e desempenho → Atualizar** mostra os sensores e a data da coleta. Não requer nova instalação do APK: a interface vem da API.

## Fontes e limites

- `Get-StorageReliabilityCounter`: temperatura atual dos discos que oferecem o contador, em °C. Zero, nulo e máximos não suportados não viram leituras.
- `MSAcpi_ThermalZoneTemperature`: zona térmica genérica, convertida de décimos de kelvin para °C: `valor / 10 - 273,15`. **Não é identificada como temperatura interna do processador.** O firmware pode fornecer valores pouco representativos ou constantes.
- CPU, GPU, RAM, placa-mãe e bateria aparecem como indisponíveis: esta versão não implementa seus provedores. Não afirma que esses componentes estão frios, normais ou seguros.

Em uma VM, os sensores físicos podem estar ausentes. Nenhuma medição é estimada. A coleta por minuto não detecta todos os picos e não substitui proteção térmica do hardware.

Fontes primárias: [Windows Storage](https://learn.microsoft.com/en-us/powershell/module/storage/get-storagereliabilitycounter), [ACPI e zonas térmicas](https://learn.microsoft.com/en-us/windows-hardware/design/device-experiences/design-guide). A implementação não instala drivers adicionais. Provedores como LibreHardwareMonitor exigem avaliação separada de acesso ao hardware e autorização para eventual driver; nenhum WinRing0/PawnIO foi instalado.

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
