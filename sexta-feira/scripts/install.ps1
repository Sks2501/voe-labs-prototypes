[CmdletBinding()]
param(
  [string]$Python = '',
  [string]$RuntimeRoot = (Join-Path (Split-Path -Parent $PSScriptRoot) '.runtime'),
  [ValidateRange(1024,65535)][int]$Port = 8765,
  [switch]$SkipWeights,
  [switch]$InstallService,
  [string]$WinSWPath = '',
  [ValidatePattern('^$|^[0-9a-fA-F]{64}$')][string]$WinSWSha256 = ''
)
$ErrorActionPreference='Stop'
function Get-SextaSourceRevision {
  param([Parameter(Mandatory=$true)][string]$ProjectDirectory)
  $fallback='source-package'
  try {
    # The project lives directly below its repository root. Never inherit an
    # unrelated Git repository from a higher ancestor of an extracted package.
    $expectedRoot=[IO.Path]::GetFullPath((Split-Path -Parent $ProjectDirectory)).TrimEnd('\')
    if (-not (Test-Path -LiteralPath (Join-Path $expectedRoot '.git'))) { return $fallback }
    $git=Get-Command git.exe -CommandType Application -ErrorAction SilentlyContinue
    if (-not $git) { return $fallback }
    # Windows PowerShell 5.1 can turn native stderr into a terminating error
    # under ErrorActionPreference=Stop, including when stderr is redirected.
    $top=@(& $git.Source -C $ProjectDirectory rev-parse --show-toplevel 2>$null)
    if ($LASTEXITCODE -ne 0 -or $top.Count -ne 1) { return $fallback }
    $actualRoot=[IO.Path]::GetFullPath([string]$top[0]).TrimEnd('\')
    if (-not $actualRoot.Equals($expectedRoot,[StringComparison]::OrdinalIgnoreCase)) { return $fallback }
    $head=@(& $git.Source -C $ProjectDirectory rev-parse HEAD 2>$null)
    if ($LASTEXITCODE -eq 0 -and $head.Count -eq 1 -and $head[0] -match '^[0-9a-fA-F]{40}$') { return [string]$head[0] }
  } catch {
    # A source archive remains installable without Git metadata or Git itself.
    return $fallback
  }
  return $fallback
}
$project = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$runtime = [IO.Path]::GetFullPath($RuntimeRoot)
if ($runtime -eq [IO.Path]::GetPathRoot($runtime)) { throw 'RuntimeRoot cannot be a drive root.' }
if (-not (Test-Path -LiteralPath (Join-Path $project 'sexta_feira\__main__.py'))) { throw 'Project directory not found.' }
$marker = Join-Path $runtime '.sexta-runtime'
if ((Test-Path -LiteralPath $runtime) -and -not (Test-Path -LiteralPath $marker) -and @(Get-ChildItem -LiteralPath $runtime -Force).Count -gt 0) { throw 'RuntimeRoot is not an identified SEXTA-FEIRA runtime. Choose a new empty directory.' }
if ((Test-Path -LiteralPath $marker) -and (Get-Content -LiteralPath $marker -Raw).Trim() -ne $project) { throw 'Runtime belongs to a different project checkout; no changes performed.' }
$driveName = [IO.Path]::GetPathRoot($runtime).TrimEnd('\').TrimEnd(':')
$drive = Get-PSDrive -Name $driveName
if ($drive.Free -lt 5GB) { throw 'At least 5 GB free are required on the runtime volume. Use -RuntimeRoot on a volume with enough space.' }
$os=Get-CimInstance Win32_OperatingSystem
if ($os.TotalVisibleMemorySize -lt 3GB/1KB) { throw 'At least 3 GB visible RAM required; shared server needs additional headroom.' }
if ($os.FreePhysicalMemory -lt 1800MB/1KB) { throw 'At least 1.8 GB currently free RAM required. Preserve production workloads.' }
if (@(Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue).Count -gt 0) { throw 'Selected port is already listening. Do not stop the owning service; choose another port.' }
. (Join-Path $PSScriptRoot "python.ps1")
$Python=Find-SextaPython -Requested $Python
New-Item -ItemType Directory -Path $runtime -Force | Out-Null
$identity=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value
& icacls.exe $runtime /inheritance:r /grant:r "*$($identity):(OI)(CI)F" '*S-1-5-18:(OI)(CI)F' '*S-1-5-32-544:(OI)(CI)F' '*S-1-5-19:(OI)(CI)RX' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Runtime ACL protection failed.' }
Set-Content -LiteralPath $marker -Value $project -Encoding UTF8
foreach ($name in @('data','models','logs','temp','diagnostics','service')) { New-Item -ItemType Directory -Path (Join-Path $runtime $name) -Force | Out-Null }
foreach ($name in @('data','logs','temp')) {
  & icacls.exe (Join-Path $runtime $name) /grant:r '*S-1-5-19:(OI)(CI)M' | Out-Null
  if ($LASTEXITCODE -ne 0) { throw "Cannot grant service account access to $name." }
}
$previousTemp=$env:TEMP; $previousTmp=$env:TMP
$env:TEMP=Join-Path $runtime 'temp'; $env:TMP=$env:TEMP
$env:SEXTA_DATA_DIR=Join-Path $runtime 'data'
$env:SEXTA_MODEL_DIR=Join-Path $runtime 'models'
$env:PIP_DISABLE_PIP_VERSION_CHECK='1'
$configFile=Join-Path $runtime 'config.json'
$config=@{data_dir=$env:SEXTA_DATA_DIR;model_dir=$env:SEXTA_MODEL_DIR;port=$Port;project_dir=$project;venv_python=(Join-Path $runtime 'venv\Scripts\python.exe')}
if (Test-Path -LiteralPath $configFile) {
  $old=Get-Content -LiteralPath $configFile -Raw | ConvertFrom-Json
  if ($old.data_dir -ne $config.data_dir -or $old.model_dir -ne $config.model_dir -or $old.port -ne $Port) { throw 'Existing configuration differs. Preserve it and perform a documented migration first.' }
} else { $config | ConvertTo-Json | Set-Content -LiteralPath $configFile -Encoding UTF8 }
$venvPython=$config.venv_python
$report=[ordered]@{started_utc=(Get-Date).ToUniversalTime().ToString('o');dependencies='pending';weights='pending';database='pending';tests='pending';service='not_installed';inference='pending';cloudflare='not_changed'}
Push-Location $project
try {
  & (Join-Path $PSScriptRoot 'audit.ps1') -OutputDirectory (Join-Path $runtime 'diagnostics')
  if (-not (Test-Path -LiteralPath $venvPython)) { & $Python -m venv (Join-Path $runtime 'venv'); if ($LASTEXITCODE -ne 0) { throw 'Virtual environment creation failed.' } }
  & $venvPython -m pip install --no-cache-dir --no-deps -c (Join-Path $project 'constraints.txt') 'torch==2.9.1' --index-url https://download.pytorch.org/whl/cpu
  if ($LASTEXITCODE -ne 0) { throw 'CPU-only PyTorch installation failed.' }
  & $venvPython -m pip install --no-cache-dir -c (Join-Path $project 'constraints.txt') -r (Join-Path $project 'requirements.txt')
  if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed. Existing files were preserved.' }
  & $venvPython -m pip check
  if ($LASTEXITCODE -ne 0) { throw 'Dependency compatibility check failed.' }
  $report.dependencies='passed'
  & $venvPython -m pip freeze | Set-Content -LiteralPath (Join-Path $runtime 'diagnostics\dependencies-installed.txt') -Encoding UTF8
  $report.python_version=(& $venvPython -c 'import sys; print(sys.version.split()[0])')
  $report.git_revision=Get-SextaSourceRevision -ProjectDirectory $project
  & $venvPython -m sexta_feira init
  if ($LASTEXITCODE -ne 0) { throw 'SQLite or private credential initialization failed.' }
  $report.database='initialized'
  if (-not $SkipWeights) {
    & $venvPython -m sexta_feira download --model small
    if ($LASTEXITCODE -ne 0) { throw 'Official model download or validation failed.' }
    $report.weights='download_verified'
  } else { $report.weights='skipped_explicitly' }
  # unittest normally writes successful progress to stderr. Windows PowerShell
  # 5.1 can treat that as NativeCommandError when an installer is piped to a log.
  & $venvPython (Join-Path $PSScriptRoot 'run_tests.py')
  if ($LASTEXITCODE -ne 0) { throw 'Automated tests failed; service was not installed.' }
  $report.tests='passed (read test output for skipped cases)'
  if (-not $SkipWeights) {
    & $venvPython (Join-Path $PSScriptRoot 'smoke.py') --port $Port | Tee-Object -FilePath (Join-Path $runtime 'diagnostics\smoke.json')
    if ($LASTEXITCODE -ne 0) { throw 'Real inference/API smoke failed; service was not installed.' }
    $report.inference='passed_real_local'
  } else { $report.inference='pending_weights' }
  if ($InstallService) {
    if ($SkipWeights) { throw 'Cannot install service before real model smoke validation.' }
    & (Join-Path $PSScriptRoot 'service.ps1') -Action Install -RuntimeRoot $runtime -WinSWPath $WinSWPath -WinSWSha256 $WinSWSha256
    $report.service='installed_not_started'
  }
  $report.completed_utc=(Get-Date).ToUniversalTime().ToString('o')
  Write-Output 'Environment prepared. See private installation report. Service and Cloudflare need their own verified activation.'
} catch {
  $report.failure=$_.Exception.Message
  throw
} finally {
  $report | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $runtime 'diagnostics\installation.json') -Encoding UTF8
  Pop-Location
  $env:TEMP=$previousTemp; $env:TMP=$previousTmp
}
