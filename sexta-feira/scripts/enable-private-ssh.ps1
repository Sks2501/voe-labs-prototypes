# One-time, explicitly authorized administrative bootstrap. Windows PowerShell 5.1.
[CmdletBinding()]
param([Parameter(Mandatory=$true)][ValidatePattern('^ssh-ed25519 [A-Za-z0-9+/=]+(?: [A-Za-z0-9._-]+)?$')][string]$PublicKey, [switch]$AdoptInactiveDefault)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'Run in an elevated PowerShell session.' }
$account = $identity.Name.Split('\')[-1].ToLowerInvariant()
if ($account -notmatch '^[a-z0-9._-]+$') { throw 'Account name requires manual SSH review.' }
$rdp = @(Get-NetTCPConnection -State Established -LocalPort 3389 -ErrorAction Stop | Where-Object { $_.RemoteAddress -notin @('127.0.0.1','::1') })
$peers = @($rdp.RemoteAddress | Select-Object -Unique)
$locals = @($rdp.LocalAddress | Select-Object -Unique)
if ($peers.Count -ne 1 -or $locals.Count -ne 1) { throw 'Expected exactly one RDP peer and one local address.' }
$peer = $peers[0]; $listen = $locals[0]
if ([Net.IPAddress]::Parse($peer).AddressFamily -ne [Net.Sockets.AddressFamily]::InterNetwork -or [Net.IPAddress]::Parse($listen).AddressFamily -ne [Net.Sockets.AddressFamily]::InterNetwork) { throw 'This bootstrap requires IPv4.' }
$sshRoot = Join-Path $env:ProgramData 'ssh'
$reportRoot = Join-Path $env:ProgramData 'SextaFeiraSshSetup'
$ruleName = 'SextaFeira-Private-SSH'
$previousService = Get-Service sshd -ErrorAction SilentlyContinue
if ($previousService -and (-not $AdoptInactiveDefault -or $previousService.Status -ne 'Stopped')) { throw 'Existing SSH service detected; review it without replacement.' }
if ((Test-Path -LiteralPath $sshRoot) -and -not $AdoptInactiveDefault) { throw 'Existing SSH directory detected; review it without replacement.' }
if ($AdoptInactiveDefault) {
    if (-not $previousService -or $previousService.StartType -ne 'Disabled') { throw 'Only a stopped, disabled default SSH service may be adopted.' }
    $existingConfig = Join-Path $sshRoot 'sshd_config'
    $allowedDefaults = @('AuthorizedKeysFile .ssh/authorized_keys','Subsystem sftp sftp-server.exe','Match Group administrators','AuthorizedKeysFile __PROGRAMDATA__/ssh/administrators_authorized_keys')
    foreach ($line in (Get-Content -LiteralPath $existingConfig)) {
        $normalized = ($line.Trim() -replace '\s+', ' ')
        if ($normalized -and -not $normalized.StartsWith('#') -and $normalized -notin $allowedDefaults) { throw 'Non-default SSH configuration requires manual review.' }
    }
    if (Test-Path -LiteralPath (Join-Path $sshRoot 'administrators_authorized_keys')) { throw 'Existing administrator authorized keys require manual review.' }
}
if (Test-Path -LiteralPath $reportRoot) { throw 'Existing setup report detected; review before retry.' }
if (Get-NetFirewallRule -Name $ruleName -ErrorAction SilentlyContinue) { throw 'Existing rule detected.' }
if (Get-NetTCPConnection -State Listen -LocalPort 22 -ErrorAction SilentlyContinue) { throw 'Port 22 is already occupied.' }
$initialRules = @(Get-NetFirewallRule | Select-Object -ExpandProperty Name)
$initialCapability = Get-WindowsCapability -Online -Name 'OpenSSH.Server~~~~0.0.1.0'
$report = [ordered]@{ started_utc = [DateTime]::UtcNow.ToString('o'); user = $account; listen = $listen; peer = $peer; initial_capability = [string]$initialCapability.State; status = 'preparing'; reboot_needed = $false }
function Set-PrivateAcl([string]$Path, [bool]$Directory) {
    $acl = if ($Directory) { New-Object Security.AccessControl.DirectorySecurity } else { New-Object Security.AccessControl.FileSecurity }
    $acl.SetAccessRuleProtection($true, $false)
    $acl.SetOwner((New-Object Security.Principal.SecurityIdentifier('S-1-5-32-544')))
    foreach ($sidText in @('S-1-5-18','S-1-5-32-544')) {
        $sid = New-Object Security.Principal.SecurityIdentifier($sidText)
        if ($Directory) { $rule = New-Object Security.AccessControl.FileSystemAccessRule($sid, 'FullControl', 'ContainerInherit,ObjectInherit', 'None', 'Allow') }
        else { $rule = New-Object Security.AccessControl.FileSystemAccessRule($sid, 'FullControl', 'Allow') }
        $acl.AddAccessRule($rule)
    }
    Set-Acl -LiteralPath $Path -AclObject $acl
}
New-Item -ItemType Directory -Path $reportRoot | Out-Null
Set-PrivateAcl $reportRoot $true
if ($AdoptInactiveDefault) {
    Copy-Item -LiteralPath $existingConfig -Destination (Join-Path $reportRoot 'sshd_config.before')
    (Get-Acl -LiteralPath $sshRoot).Sddl | Set-Content -LiteralPath (Join-Path $reportRoot 'ssh-directory-acl.before.txt')
}
function Save-Report { $report | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $reportRoot 'report.json') -Encoding UTF8 }
Save-Report
$createdRule = $false
$disabledExistingRules = @()
try {
    if ($initialCapability.State -ne 'Installed') {
        $result = Add-WindowsCapability -Online -Name 'OpenSSH.Server~~~~0.0.1.0'
        $report.reboot_needed = [bool]$result.RestartNeeded
    }
    # Windows may create a broad inbound rule while adding the component.
    # Disable only rules introduced by this installation, before starting sshd.
    $newRules = @(Get-NetFirewallRule | Where-Object { $_.Name -notin $initialRules -and $_.Name -like 'OpenSSH*' })
    foreach ($rule in $newRules) { $rule | Disable-NetFirewallRule | Out-Null }
    $report['disabled_new_rules'] = @($newRules | ForEach-Object { $_.Name })
    if ($AdoptInactiveDefault) {
        $disabledExistingRules = @(Get-NetFirewallRule | Where-Object { $_.Name -in $initialRules -and $_.Name -like 'OpenSSH*' -and $_.Enabled -eq 'True' })
        $report['disabled_previous_ssh_rules'] = @($disabledExistingRules | ForEach-Object { $_.Name })
        foreach ($rule in $disabledExistingRules) { $rule | Disable-NetFirewallRule | Out-Null }
    }
    if ($report.reboot_needed) { throw 'Component requests a reboot; no reboot performed.' }
    $sshd = Join-Path $env:WINDIR 'System32\OpenSSH\sshd.exe'
    $keygen = Join-Path $env:WINDIR 'System32\OpenSSH\ssh-keygen.exe'
    if (-not (Test-Path -LiteralPath $sshd)) { throw 'OpenSSH server executable unavailable.' }
    New-Item -ItemType Directory -Path $sshRoot -Force | Out-Null
    if (-not $AdoptInactiveDefault) { Set-PrivateAcl $sshRoot $true }
    $config = @(
        'Port 22', "ListenAddress $listen", 'HostKey __PROGRAMDATA__/ssh/ssh_host_ed25519_key',
        'PubkeyAuthentication yes', 'PasswordAuthentication no', 'ChallengeResponseAuthentication no',
        'AuthenticationMethods publickey', 'AuthorizedKeysFile __PROGRAMDATA__/ssh/administrators_authorized_keys',
        "AllowUsers $account@$peer", 'StrictModes yes', 'PermitEmptyPasswords no',
        'AllowTcpForwarding no', 'AllowAgentForwarding no', 'PermitTTY no',
        'MaxAuthTries 3', 'MaxSessions 2', 'LoginGraceTime 20', 'LogLevel INFO',
        'Subsystem sftp sftp-server.exe'
    ) -join "`r`n"
    $configPath = Join-Path $sshRoot 'sshd_config'
    [IO.File]::WriteAllText($configPath, $config + "`r`n", [Text.Encoding]::ASCII)
    $keysPath = Join-Path $sshRoot 'administrators_authorized_keys'
    [IO.File]::WriteAllText($keysPath, ('from="' + $peer + '",no-agent-forwarding,no-port-forwarding,no-pty ' + $PublicKey + "`r`n"), [Text.Encoding]::ASCII)
    Set-PrivateAcl $configPath $false
    Set-PrivateAcl $keysPath $false
    & $keygen -A
    if ($LASTEXITCODE -ne 0) { throw 'Host-key generation failed.' }
    & $sshd -t -f $configPath
    if ($LASTEXITCODE -ne 0) { throw 'SSH configuration validation failed.' }
    New-NetFirewallRule -Name $ruleName -DisplayName 'SEXTA-FEIRA private administrative SSH' -Direction Inbound -Action Allow -Protocol TCP -LocalPort 22 -LocalAddress $listen -RemoteAddress $peer -Profile Any | Out-Null
    $createdRule = $true
    Set-Service -Name sshd -StartupType Automatic
    Start-Service -Name sshd
    $service = Get-Service sshd
    if ($service.Status -ne 'Running') { throw 'SSH did not reach Running.' }
    $fingerprint = & $keygen -lf (Join-Path $sshRoot 'ssh_host_ed25519_key.pub') -E sha256
    if ($LASTEXITCODE -ne 0) { throw 'Host fingerprint unavailable.' }
    $report['host_fingerprint'] = [string]$fingerprint
    $report['host_public_key'] = [IO.File]::ReadAllText((Join-Path $sshRoot 'ssh_host_ed25519_key.pub')).Trim()
    $report.status = 'running_key_only_restricted'
    Save-Report
    Write-Host "SSH READY user=$account listen=$listen peer=$peer"
    Write-Host $fingerprint
    Write-Host "Report: $reportRoot\report.json"
} catch {
    $failure = $_.Exception.Message
    # Stop only the SSH service introduced by this script. Preserve artifacts for audit.
    $newService = Get-Service sshd -ErrorAction SilentlyContinue
    if ($newService) { Stop-Service sshd -ErrorAction SilentlyContinue; Set-Service sshd -StartupType Disabled -ErrorAction SilentlyContinue }
    if ($createdRule) { Disable-NetFirewallRule -Name $ruleName -ErrorAction SilentlyContinue | Out-Null }
    if ($AdoptInactiveDefault) { Copy-Item -LiteralPath (Join-Path $reportRoot 'sshd_config.before') -Destination $existingConfig -Force }
    foreach ($rule in $disabledExistingRules) { $rule | Enable-NetFirewallRule -ErrorAction SilentlyContinue | Out-Null }
    Get-NetFirewallRule -ErrorAction SilentlyContinue | Where-Object { $_.Name -notin $initialRules -and $_.Name -like 'OpenSSH*' } | Disable-NetFirewallRule -ErrorAction SilentlyContinue | Out-Null
    $report.status = 'failed_service_disabled'; $report['error'] = $failure
    Save-Report
    throw $failure
}
