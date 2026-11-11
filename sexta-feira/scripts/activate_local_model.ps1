[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$RuntimeRoot,[Parameter(Mandatory=$true)][string]$SourceDirectory)
$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
$runtime=[IO.Path]::GetFullPath($RuntimeRoot).TrimEnd('\')
$configPath=Join-Path $runtime 'config.json'
$config=Get-Content -LiteralPath $configPath -Raw|ConvertFrom-Json
$project=[IO.Path]::GetFullPath($config.project_dir).TrimEnd('\')
$source=[IO.Path]::GetFullPath($SourceDirectory).TrimEnd('\')
if((Get-Content (Join-Path $runtime '.sexta-runtime') -Raw).Trim() -ne $project){throw 'Identified runtime/source mismatch.'}
$owner=Get-CimInstance Win32_Service -Filter "Name='SextaFeira'"
if(-not $owner -or $owner.PathName.Trim('"') -ne (Join-Path $runtime 'service\SextaFeira.exe')){throw 'Application service identity mismatch.'}
if(Get-Service SextaFeiraInference -ErrorAction SilentlyContinue){throw 'Native service already exists; use controlled maintenance, not reinstall.'}
if(Get-NetTCPConnection -State Listen -LocalPort 18765 -ErrorAction SilentlyContinue){throw 'Native port occupied. No process was stopped.'}
$files=@('sexta_feira\brain.py','sexta_feira\inference_llama.py','sexta_feira\observability.py','sexta_feira\server.py','sexta_feira\storage.py',
 'sexta_feira\web\app.js','sexta_feira\web\index.html','sexta_feira\web\styles.css','scripts\service_runner.py','scripts\native_runner.py','scripts\start.ps1',
 'scripts\prepare_local_model.py','scripts\activate_local_model.ps1','tests\test_native_inference.py')
foreach($file in $files){if(-not(Test-Path -LiteralPath (Join-Path $source $file))){throw "Missing source file: $file"}}
$credential=(Get-Content (Join-Path $config.data_dir 'access.token') -Raw).Trim()
$headers=@{Authorization="Bearer $credential"}
$uri="http://127.0.0.1:$($config.port)/api/v1"
$backup=Invoke-RestMethod "$uri/admin/backup" -Method Post -Headers $headers -ContentType 'application/json' -Body '{}' -TimeoutSec 15
if($backup.integrity -ne 'ok'){throw 'Database backup did not pass integrity.'}
$stamp=Get-Date -Format 'yyyyMMdd-HHmmss'
$backupDirectory=Join-Path $runtime ('updates\local-model-'+$stamp)
New-Item -ItemType Directory -Path $backupDirectory|Out-Null
Copy-Item -LiteralPath $configPath -Destination (Join-Path $backupDirectory 'config.before.json')
foreach($file in $files){$old=Join-Path $project $file;if(Test-Path -LiteralPath $old){$target=Join-Path $backupDirectory $file;New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force|Out-Null;Copy-Item -LiteralPath $old -Destination $target}}
$tunnel=Get-CimInstance Win32_Service -Filter "Name='SextaFeiraTunnel'"
if($tunnel -and $tunnel.PathName.Trim('"') -ne (Join-Path $runtime 'service\SextaFeiraTunnel.exe')){throw 'Dedicated tunnel service identity mismatch.'}
$tunnelWasRunning=$tunnel -and $tunnel.State -eq 'Running'
$productionBefore=(Get-CimInstance Win32_Service -Filter "Name='Cloudflared'").ProcessId
$key=Join-Path $config.data_dir 'inference.token'
if(-not(Test-Path -LiteralPath $key) -or (Get-Content -LiteralPath $key -Raw).Trim().Length -lt 32){throw 'Prepared private inference credential missing.'}
$config|Add-Member -NotePropertyName native_token_file -NotePropertyValue $key -Force
$config|Add-Member -NotePropertyName native_url -NotePropertyValue 'http://127.0.0.1:18765' -Force
$stopped=$false
try{
 for($attempt=0;$attempt -lt 30;$attempt++){
  $state=Invoke-RestMethod "$uri/model" -Headers $headers -TimeoutSec 5
  if(-not $state.processing -and $state.queue_depth -eq 0){break}
  if($attempt -eq 29){throw 'Wait for pending conversations before maintenance.'}
  Start-Sleep -Seconds 2
 }
 if($tunnelWasRunning){& (Join-Path $runtime 'service\SextaFeiraTunnel.exe') stop;if($LASTEXITCODE){throw 'Dedicated tunnel stop failed.'};(Get-Service SextaFeiraTunnel).WaitForStatus('Stopped',[TimeSpan]::FromSeconds(60))}
 & (Join-Path $runtime 'service\SextaFeira.exe') stop
 if($LASTEXITCODE){throw 'Application stop failed.'}
 (Get-Service SextaFeira).WaitForStatus('Stopped',[TimeSpan]::FromSeconds(90))
 $stopped=$true
 foreach($file in $files){$target=Join-Path $project $file;Copy-Item -LiteralPath (Join-Path $source $file) -Destination $target -Force}
 # stdin avoids Windows PowerShell 5.1 stripping nested quotes in native -c arguments.
 $lookup='import sqlite3,sys;c=sqlite3.connect(sys.argv[1]);print(c.execute("SELECT coalesce(max(id),0) FROM messages").fetchone()[0]);c.close()'
 $last=$lookup | & $config.venv_python -I -B - (Join-Path $config.data_dir 'memory.sqlite3')
 if($LASTEXITCODE){throw 'History cutover lookup failed.'}
 $config|Add-Member -NotePropertyName history_after_id -NotePropertyValue ([long]$last) -Force
 $config|Add-Member -NotePropertyName backend -NotePropertyValue 'llama.cpp' -Force
 $config|ConvertTo-Json -Depth 6|Set-Content -LiteralPath $configPath -Encoding UTF8
 $wrapper=Join-Path $runtime 'service\SextaFeira.exe'
 if((Get-FileHash $wrapper).Hash -ne '05b82d46ad331cc16bdc00de5c6332c1ef818df8ceefcd49c726553209b3a0da'){throw 'Verified WinSW wrapper required.'}
 $native=Join-Path $runtime 'service\SextaFeiraInference.exe'
 $nativeXml=Join-Path $runtime 'service\SextaFeiraInference.xml'
 if((Test-Path $native) -or (Test-Path $nativeXml)){throw 'Native service artifacts already exist; preserved for review.'}
 Copy-Item -LiteralPath $wrapper -Destination $native
 $escape={param($s)[Security.SecurityElement]::Escape([string]$s)}
 $pythonXml=& $escape $config.venv_python;$runnerXml=& $escape (Join-Path $project 'scripts\native_runner.py');$configXml=& $escape $configPath
 $projectXml=& $escape $project;$logsXml=& $escape (Join-Path $runtime 'logs\inference')
 New-Item -ItemType Directory -Path (Join-Path $runtime 'logs\inference') -Force|Out-Null
 @"
<service>
 <id>SextaFeiraInference</id><name>SEXTA-FEIRA Local Model</name>
 <description>Offline quantized model, CPU only, authenticated loopback. No paid inference.</description>
 <executable>$pythonXml</executable><startarguments>-B &quot;$runnerXml&quot; run &quot;$configXml&quot;</startarguments>
 <stopexecutable>$pythonXml</stopexecutable><stoparguments>-B &quot;$runnerXml&quot; stop</stoparguments>
 <workingdirectory>$projectXml</workingdirectory>
 <serviceaccount><domain>NT AUTHORITY</domain><user>LocalService</user></serviceaccount>
 <priority>BelowNormal</priority><startmode>Automatic</startmode><delayedAutoStart/>
 <stoptimeout>30 sec</stoptimeout><onfailure action="restart" delay="5 sec"/><onfailure action="restart" delay="30 sec"/><onfailure action="none"/>
 <resetfailure>1 hour</resetfailure><logpath>$logsXml</logpath>
 <log mode="roll-by-size"><sizeThreshold>1024</sizeThreshold><keepFiles>3</keepFiles></log>
 <env name="PYTHONNOUSERSITE" value="1"/><env name="PYTHONDONTWRITEBYTECODE" value="1"/>
</service>
"@|Set-Content -LiteralPath $nativeXml -Encoding UTF8
 & $native install
 if($LASTEXITCODE){throw 'Native service installation failed.'}
 & $native start
 if($LASTEXITCODE){throw 'Native service startup failed.'}
 $nativeKey=(Get-Content -LiteralPath $key -Raw).Trim()
 $nativeReady=$false
 for($attempt=0;$attempt -lt 60;$attempt++){
  try{$ready=Invoke-RestMethod 'http://127.0.0.1:18765/health' -Headers @{Authorization="Bearer $nativeKey"} -TimeoutSec 2;if($ready.status -eq 'ok'){$nativeReady=$true;break}}catch{}
  Start-Sleep -Seconds 1
 }
 if(-not $nativeReady){throw 'Native service readiness failed.'}
 $nativeKey=$null
 & (Join-Path $runtime 'service\SextaFeira.exe') start
 if($LASTEXITCODE){throw 'API startup failed.'}
 (Get-Service SextaFeira).WaitForStatus('Running',[TimeSpan]::FromSeconds(30))
 Start-Sleep -Seconds 2
 & (Join-Path $project 'scripts\health.ps1') -RuntimeRoot $runtime
 if($tunnelWasRunning){& (Join-Path $runtime 'service\SextaFeiraTunnel.exe') start;if($LASTEXITCODE){throw 'Dedicated tunnel restart failed.'}}
 $productionAfter=(Get-CimInstance Win32_Service -Filter "Name='Cloudflared'").ProcessId
 @{backend='llama.cpp';model='Gemma 3 4B IT Q4_K_M';database_backup=$backup.backup;source_backup=$backupDirectory;history_after_id=$config.history_after_id;production_tunnel_pid_before=$productionBefore;production_tunnel_pid_after=$productionAfter;activated_utc=[DateTime]::UtcNow.ToString('o')}|ConvertTo-Json|Set-Content (Join-Path $runtime 'diagnostics\local-model-activation.json') -Encoding UTF8
 Write-Output 'Local model activated. Existing history/data preserved; production tunnel not restarted.'
}catch{
 $failure=$_.Exception.Message
 if($stopped){
  # Restore only the explicit project files/config. Database schema remains 2;
  # never restore its snapshot over conversations written after the backup.
  if((Get-Service SextaFeira).Status -eq 'Running'){& (Join-Path $runtime 'service\SextaFeira.exe') stop}
  (Get-Service SextaFeira).WaitForStatus('Stopped',[TimeSpan]::FromSeconds(90))
  foreach($file in $files){$saved=Join-Path $backupDirectory $file;if(Test-Path -LiteralPath $saved){Copy-Item -LiteralPath $saved -Destination (Join-Path $project $file) -Force}}
  Copy-Item -LiteralPath (Join-Path $backupDirectory 'config.before.json') -Destination $configPath -Force
  if(Get-Service SextaFeiraInference -ErrorAction SilentlyContinue){Stop-Service SextaFeiraInference -ErrorAction SilentlyContinue;Set-Service SextaFeiraInference -StartupType Disabled -ErrorAction SilentlyContinue}
  if((Get-Service SextaFeira).Status -ne 'Running'){Start-Service SextaFeira}
  if($tunnelWasRunning -and (Get-Service SextaFeiraTunnel).Status -ne 'Running'){Start-Service SextaFeiraTunnel}
 }
 throw $failure
}finally{$credential=$null;$headers=$null}
