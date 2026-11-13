[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$RuntimeRoot,
 [ValidateSet('Plan','Apply','Undo')][string]$Action='Plan',[string]$PlanFile='')
$ErrorActionPreference='Stop'
$runtime=[IO.Path]::GetFullPath($RuntimeRoot).TrimEnd('\')
$project=[IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot)).TrimEnd('\')
if(-not(Test-Path -LiteralPath (Join-Path $runtime '.sexta-runtime')) -or (Get-Content (Join-Path $runtime '.sexta-runtime') -Raw).Trim() -ne $project){throw 'Identified private runtime required'}
$diagnostics=[IO.Path]::GetFullPath((Join-Path (Split-Path $runtime -Parent) 'SextaFeiraDiagnostics')).TrimEnd('\')
$maintenance=Join-Path $runtime 'maintenance'
$archive=Join-Path $runtime 'archive'
$allowed=@('android-source-stage.zip','chat-workspace-stage.zip','ios-ui-stage.zip','modern-stage.zip',
 'SEXTA-FEIRA-CONVERSAS.zip','SEXTA-FEIRA-MODERNA.zip','temperatures-source.zip','hardware-source.zip',
 'sexta-feira-android-1.0.0.apk','sexta-feira-android-1.0.1.apk')
foreach($directory in @($runtime,$diagnostics,$maintenance,$archive)){
 if(Test-Path -LiteralPath $directory){if((Get-Item -LiteralPath $directory).Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Reparse path refused'}}
}
foreach($directory in @($maintenance,$archive)){
 if(-not(Test-Path -LiteralPath $directory)){New-Item -ItemType Directory $directory|Out-Null}
 $acl=[Security.AccessControl.DirectorySecurity]::new();$acl.SetAccessRuleProtection($true,$false)
 foreach($sid in @('S-1-5-18','S-1-5-32-544')){$acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new([Security.Principal.SecurityIdentifier]::new($sid),'FullControl','ContainerInherit,ObjectInherit','None','Allow'))}
 Set-Acl -LiteralPath $directory -AclObject $acl
}
if($Action -eq 'Plan'){
 $id=[Guid]::NewGuid().ToString('N');$destination=Join-Path $archive ('installers-'+(Get-Date -Format yyyyMMdd)+'-'+$id.Substring(0,8))
 $items=@()
 foreach($name in $allowed){
  $file=Join-Path $diagnostics $name
  if(Test-Path -LiteralPath $file){$info=Get-Item -LiteralPath $file
   if($info.PSIsContainer -or ($info.Attributes -band [IO.FileAttributes]::ReparsePoint) -or $info.LastWriteTimeUtc -gt [DateTime]::UtcNow.AddHours(-1)){continue}
   $items+=@{name=$name;source=$file;destination=(Join-Path $destination $name);bytes=$info.Length;sha256=(Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash}
  }
 }
 $plan=@{schema_version=1;id=$id;runtime=$runtime;state='planned';created_utc=[DateTime]::UtcNow.ToString('o');items=@($items)}
 $PlanFile=Join-Path $maintenance ('organization-'+$id+'.json')
 $plan|ConvertTo-Json -Depth 5|Set-Content -LiteralPath $PlanFile -Encoding UTF8
 # Inventory is private and intentionally excludes command lines, configuration and file contents.
 $inventory=@{created_utc=[DateTime]::UtcNow.ToString('o');root_directories=@(Get-ChildItem -LiteralPath ([IO.Path]::GetPathRoot($runtime)) -Directory -Force|Select-Object -ExpandProperty Name);
  services=@(Get-CimInstance Win32_Service|Where-Object {$_.Name -match 'Sexta|Cloudflared|postgres|W3SVC'}|Select-Object Name,State,StartMode,StartName,ProcessId);
  listeners=@(Get-NetTCPConnection -State Listen|Where-Object LocalPort -in 3333,3334,5432,8765,18765|Select-Object LocalAddress,LocalPort,OwningProcess)}
 $inventory|ConvertTo-Json -Depth 5|Set-Content (Join-Path $maintenance 'server-inventory.json') -Encoding UTF8
 @"
# Indice de operacao do servidor

Gerado em UTC: $($plan.created_utc)

- Codigo atual da SEXTA-FEIRA: $project
- Runtime e configuracao privados: $runtime
- SQLite pessoal, credenciais e distribuicao Android: $runtime\data
- Modelos: $runtime\local-model e $runtime\models
- Ambiente Python: $runtime\venv
- Servicos e tunel proprios: $runtime\service e $runtime\cloudflare
- Logs com rotacao: $runtime\logs e $runtime\data\logs
- Sensores: $runtime\sensors e $runtime\sensor-provider
- Backups de atualizacao/reversao preservados: $runtime\updates
- Inventario privado: $maintenance\server-inventory.json
- Plano reversivel de arquivo: $PlanFile
- Copias antigas de instaladores: $destination

Pastas Team Bike e Windows foram apenas inventariadas.
Nenhuma pasta de producao, banco, modelo, credencial ou configuracao ativa e movida.
Apply/Undo aceita somente as dez copias de instaladores nomeadas no script.
O arquivo preserva todos os bytes; mover no mesmo volume nao libera espaco em disco.
"@|Set-Content (Join-Path $maintenance 'OPERACAO.md') -Encoding UTF8
 $totalBytes=0;foreach($item in $items){$totalBytes+=$item.bytes}
 @{plan=$PlanFile;count=$items.Count;bytes=$totalBytes}|ConvertTo-Json -Compress
 exit 0
}
$PlanFile=[IO.Path]::GetFullPath($PlanFile)
if(-not $PlanFile.StartsWith($maintenance+'\',[StringComparison]::OrdinalIgnoreCase) -or (Get-Item -LiteralPath $PlanFile).Length -gt 65536){throw 'Plan outside private maintenance directory'}
if((Get-Item -LiteralPath $PlanFile).Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Reparse plan refused'}
$plan=Get-Content -LiteralPath $PlanFile -Raw|ConvertFrom-Json
if($plan.schema_version -ne 1 -or $plan.runtime -ne $runtime -or $plan.id -notmatch '^[a-f0-9]{32}$' -or @($plan.items).Count -gt 10){throw 'Invalid organization plan'}
if(($Action -eq 'Apply' -and $plan.state -eq 'applied') -or ($Action -eq 'Undo' -and $plan.state -eq 'undone')){Write-Output 'Requested organization state already satisfied';exit 0}
if(($Action -eq 'Apply' -and $plan.state -notin @('planned','undone')) -or ($Action -eq 'Undo' -and $plan.state -ne 'applied')){throw 'Unexpected plan state'}
foreach($item in $plan.items){
 if($item.name -notin $allowed -or $item.source -ne (Join-Path $diagnostics $item.name)){throw 'Unrelated source preserved'}
 $destination=[IO.Path]::GetFullPath($item.destination)
 if(-not $destination.StartsWith($archive+'\',[StringComparison]::OrdinalIgnoreCase) -or [IO.Path]::GetFileName($destination) -ne $item.name){throw 'Archive path refused'}
 $parent=[IO.Path]::GetDirectoryName($destination)
 if([IO.Path]::GetDirectoryName($parent) -ne $archive -or [IO.Path]::GetFileName($parent) -notmatch ('^installers-[0-9]{8}-'+$plan.id.Substring(0,8)+'$')){throw 'Nested archive path refused'}
 $from=if($Action -eq 'Apply'){$item.source}else{$destination};$to=if($Action -eq 'Apply'){$destination}else{$item.source}
 if((Get-Item -LiteralPath $from).Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Reparse file refused'}
 if(Test-Path -LiteralPath $to){throw 'Existing target preserved'}
 if((Get-FileHash -LiteralPath $from -Algorithm SHA256).Hash -ne $item.sha256){throw 'Installer hash mismatch; nothing moved'}
}
$moved=@()
try{
 foreach($item in $plan.items){
  $from=if($Action -eq 'Apply'){$item.source}else{$item.destination};$to=if($Action -eq 'Apply'){$item.destination}else{$item.source}
  $parent=Split-Path $to -Parent
  if(Test-Path -LiteralPath $parent){if((Get-Item -LiteralPath $parent).Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Reparse archive directory refused'}}else{New-Item -ItemType Directory $parent|Out-Null}
  Move-Item -LiteralPath $from -Destination $to
  $moved+=@{source=$from;destination=$to}
 }
 $plan.state=if($Action -eq 'Apply'){'applied'}else{'undone'}
 $temporary=Join-Path $maintenance ('.organization-'+[Guid]::NewGuid().ToString('N')+'.tmp')
 [IO.File]::WriteAllText($temporary,($plan|ConvertTo-Json -Depth 5),[Text.UTF8Encoding]::new($false))
 [IO.File]::Replace($temporary,$PlanFile,[NullString]::Value)
 @{state=$plan.state;count=$moved.Count;plan=$PlanFile}|ConvertTo-Json -Compress
}catch{
 for($i=$moved.Count-1;$i -ge 0;$i--){Move-Item -LiteralPath $moved[$i].destination -Destination $moved[$i].source}
 throw
}
