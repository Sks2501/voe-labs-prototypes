[CmdletBinding()]
param([string]$OutputDirectory = (Join-Path $env:LOCALAPPDATA 'SextaFeira\diagnostics'))
$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
# Private operational inventory: never add this directory to Git.
$identity = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
& icacls.exe $OutputDirectory /inheritance:r /grant:r "*$($identity):(OI)(CI)F" '*S-1-5-18:(OI)(CI)F' '*S-1-5-32-544:(OI)(CI)F' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Cannot protect diagnostic directory ACL.' }
$os = Get-CimInstance Win32_OperatingSystem
$computer = Get-CimInstance Win32_ComputerSystem
$cpu = @(Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors)
$services = @(Get-CimInstance Win32_Service | Select-Object Name,DisplayName,State,StartMode)
$processes = @(Get-Process | Select-Object ProcessName,Id,WorkingSet64,PrivateMemorySize64,CPU)
$ports = @(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | ForEach-Object {
    $processName = (Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue).ProcessName
    [pscustomobject]@{Address=$_.LocalAddress;Port=$_.LocalPort;ProcessId=$_.OwningProcess;Process=$processName}
})
$gpu = @(Get-CimInstance Win32_VideoController | Select-Object Name,AdapterRAM,DriverVersion,Status)
$nvidia = @()
$nv = Get-Command nvidia-smi.exe -ErrorAction SilentlyContinue
if ($nv) { $nvidia = @(& $nv.Source --query-gpu=name,memory.total,driver_version --format=csv,noheader 2>$null) }
$record = [ordered]@{
    CapturedUtc=(Get-Date).ToUniversalTime().ToString('o')
    Scope='Machine where this script actually runs; does not establish access to another VPS.'
    OS=[ordered]@{Caption=$os.Caption;Version=$os.Version;VisibleRAMBytes=([long]$os.TotalVisibleMemorySize*1024);FreeRAMBytes=([long]$os.FreePhysicalMemory*1024)}
    Computer=[ordered]@{Manufacturer=$computer.Manufacturer;Model=$computer.Model;HypervisorPresent=$computer.HypervisorPresent;LogicalProcessors=$computer.NumberOfLogicalProcessors;PhysicalRAMBytes=$computer.TotalPhysicalMemory}
    VirtualizationNote='HypervisorPresent alone does not prove this OS is a VM; corroborate manufacturer/model and hypervisor inventory.'
    CPUs=$cpu
    Process=[ordered]@{Architecture=$env:PROCESSOR_ARCHITECTURE;Affinity=(Get-Process -Id $PID).ProcessorAffinity.ToInt64();WorkingSetBytes=(Get-Process -Id $PID).WorkingSet64}
    Volumes=@(Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3' | Select-Object DeviceID,Size,FreeSpace)
    GPU=$gpu
    VRAMNote='Win32 AdapterRAM can be truncated; NVIDIA memory.total is authoritative when nvidia-smi works.'
    NvidiaSmi=$nvidia
    Services=$services
    ListeningPorts=$ports
    Processes=$processes
    CloudflareConfigPresent=[bool](Test-Path -LiteralPath (Join-Path $env:USERPROFILE '.cloudflared\config.yml'))
    SecretPolicy='No service command lines, environment variable values, passwords, tunnel credentials or conversation contents collected.'
}
$file = Join-Path $OutputDirectory ('audit-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.json')
$record | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $file -Encoding UTF8
Write-Output "Private audit saved: $file"
Write-Output ("OS: {0}; logical CPUs: {1}; visible RAM: {2:N2} GB; free RAM: {3:N2} GB" -f $os.Caption,$computer.NumberOfLogicalProcessors,($os.TotalVisibleMemorySize/1MB),($os.FreePhysicalMemory/1MB))
