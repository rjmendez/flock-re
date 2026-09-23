param(
    [string[]]$Serials = @("emulator-5554", "emulator-5590"),
    [ValidateSet("apply", "remove", "status")]
    [string]$Mode = "status",
    [ValidateSet("guarded-safe", "local-reach-test")]
    [string]$Profile = "guarded-safe",
    [string]$AdbPath = "C:\Users\rjmendez-admin\development\flock-re\artifact-staging\tools\platform-tools\adb.exe"
)

if (-not (Test-Path -LiteralPath $AdbPath)) {
    throw "adb not found at '$AdbPath'"
}

$GuardProfiles = @{
    "guarded-safe" = @{
        Description = "Loopback plus pinned host gateway ports only."
        IPv4Rules   = @(
            "-d 127.0.0.0/8 -j ACCEPT",
            "-d 10.0.2.2 -p tcp --dport 14011 -j ACCEPT",
            "-d 10.0.2.2 -p tcp --dport 14021 -j ACCEPT",
            "-d 10.0.2.2 -p tcp --dport 18443 -j ACCEPT",
            "-j REJECT"
        )
        IPv6Rules   = @(
            "-d ::1/128 -j ACCEPT",
            "-j REJECT"
        )
    }
    "local-reach-test" = @{
        Description = "Loopback plus unrestricted Android host gateway reachability."
        IPv4Rules   = @(
            "-d 127.0.0.0/8 -j ACCEPT",
            "-d 10.0.2.2 -j ACCEPT",
            "-j REJECT"
        )
        IPv6Rules   = @(
            "-d ::1/128 -j ACCEPT",
            "-j REJECT"
        )
    }
}

$SelectedProfile = $GuardProfiles[$Profile]

function Invoke-AdbCommand {
    param(
        [string]$Serial,
        [string[]]$AdbArgs
    )

    $output = & $AdbPath -s $Serial @AdbArgs 2>&1
    $exitCode = $LASTEXITCODE
    [pscustomobject]@{
        ExitCode = $exitCode
        Output   = @($output | ForEach-Object { "$_" })
    }
}

function Invoke-AdbShell {
    param(
        [string]$Serial,
        [string]$Cmd
    )
    Invoke-AdbCommand -Serial $Serial -AdbArgs @("shell", $Cmd)
}

function Join-FirstLine {
    param([string[]]$Lines)
    if (-not $Lines -or $Lines.Count -eq 0) {
        return ""
    }
    return ($Lines[0]).Trim()
}

function Get-DeviceState {
    param([string]$Serial)
    $stateResult = Invoke-AdbCommand -Serial $Serial -AdbArgs @("get-state")
    $state = Join-FirstLine -Lines $stateResult.Output
    [pscustomobject]@{
        IsOnline = ($stateResult.ExitCode -eq 0 -and $state -eq "device")
        State    = $state
        ExitCode = $stateResult.ExitCode
        Output   = $stateResult.Output
    }
}

function Ensure-RootAccess {
    param([string]$Serial)
    $uidBefore = Invoke-AdbShell -Serial $Serial -Cmd "id -u"
    if ($uidBefore.ExitCode -eq 0 -and (Join-FirstLine -Lines $uidBefore.Output) -eq "0") {
        return [pscustomobject]@{ Success = $true; Message = "adbd already running as root." }
    }

    $rootResult = Invoke-AdbCommand -Serial $Serial -AdbArgs @("root")
    Start-Sleep -Milliseconds 700

    $uidAfter = Invoke-AdbShell -Serial $Serial -Cmd "id -u"
    if ($uidAfter.ExitCode -eq 0 -and (Join-FirstLine -Lines $uidAfter.Output) -eq "0") {
        return [pscustomobject]@{ Success = $true; Message = "root escalation succeeded." }
    }

    $rootLine = (Join-FirstLine -Lines $rootResult.Output)
    $uidLine = (Join-FirstLine -Lines $uidAfter.Output)
    if ([string]::IsNullOrWhiteSpace($uidLine)) {
        $uidLine = "unavailable"
    }
    return [pscustomobject]@{
        Success = $false
        Message = "root escalation failed (adb root: '$rootLine'; id -u: '$uidLine')."
    }
}

function Build-ApplyCommand {
    param(
        [string]$Tool,
        [string]$Chain,
        [string[]]$RuleSuffixes
    )
    $segments = @("$Tool -N $Chain 2>/dev/null", "$Tool -F $Chain")
    foreach ($rule in $RuleSuffixes) {
        $segments += "$Tool -A $Chain $rule"
    }
    $segments += "$Tool -C OUTPUT -j $Chain 2>/dev/null || $Tool -I OUTPUT 1 -j $Chain"
    $segments -join "; "
}

function Write-Validation {
    param(
        [string]$Serial,
        [string]$ProfileName,
        [hashtable]$ProfileSpec,
        [bool]$ExpectActive
    )

    $v4Output = Invoke-AdbShell -Serial $Serial -Cmd "iptables -S OUTPUT 2>/dev/null"
    $v4Chain = Invoke-AdbShell -Serial $Serial -Cmd "iptables -S C2_EGRESS_GUARD 2>/dev/null || echo NO_GUARD_CHAIN"
    $v6Output = Invoke-AdbShell -Serial $Serial -Cmd "ip6tables -S OUTPUT 2>/dev/null"
    $v6Chain = Invoke-AdbShell -Serial $Serial -Cmd "ip6tables -S C2_EGRESS_GUARD6 2>/dev/null || echo NO_GUARD_CHAIN6"

    Write-Host "[$serial] status:"
    $v4Output.Output | ForEach-Object { Write-Host $_ }
    $v4Chain.Output | ForEach-Object { Write-Host $_ }

    $v4Expected = @($ProfileSpec.IPv4Rules | ForEach-Object { "-A C2_EGRESS_GUARD $_" })
    $v6Expected = @($ProfileSpec.IPv6Rules | ForEach-Object { "-A C2_EGRESS_GUARD6 $_" })
    $v4Actual = @($v4Chain.Output | Where-Object { $_ -like "-A C2_EGRESS_GUARD *" })
    $v6Actual = @($v6Chain.Output | Where-Object { $_ -like "-A C2_EGRESS_GUARD6 *" })
    $v4JumpActive = @($v4Output.Output | Where-Object { $_ -eq "-A OUTPUT -j C2_EGRESS_GUARD" }).Count -gt 0
    $v6JumpActive = @($v6Output.Output | Where-Object { $_ -eq "-A OUTPUT -j C2_EGRESS_GUARD6" }).Count -gt 0
    $v4Missing = @($v4Expected | Where-Object { $_ -notin $v4Actual })
    $v6Missing = @($v6Expected | Where-Object { $_ -notin $v6Actual })
    $v4Unexpected = @($v4Actual | Where-Object { $_ -notin $v4Expected })
    $v6Unexpected = @($v6Actual | Where-Object { $_ -notin $v6Expected })

    if ($ExpectActive) {
        $isValid = $v4JumpActive -and $v6JumpActive -and $v4Missing.Count -eq 0 -and $v6Missing.Count -eq 0 -and $v4Unexpected.Count -eq 0 -and $v6Unexpected.Count -eq 0
        $state = if ($isValid) { "PASS" } else { "FAIL" }
        Write-Host "[$serial] validation ($ProfileName): $state"
        if (-not $v4JumpActive) { Write-Host "[$serial]  missing OUTPUT jump to C2_EGRESS_GUARD" }
        if (-not $v6JumpActive) { Write-Host "[$serial]  missing OUTPUT jump to C2_EGRESS_GUARD6" }
        if ($v4Missing.Count -gt 0) { Write-Host "[$serial]  missing IPv4 rules: $($v4Missing -join ' | ')" }
        if ($v6Missing.Count -gt 0) { Write-Host "[$serial]  missing IPv6 rules: $($v6Missing -join ' | ')" }
        if ($v4Unexpected.Count -gt 0) { Write-Host "[$serial]  unexpected IPv4 rules: $($v4Unexpected -join ' | ')" }
        if ($v6Unexpected.Count -gt 0) { Write-Host "[$serial]  unexpected IPv6 rules: $($v6Unexpected -join ' | ')" }
    }
    else {
        $isRemoved = (-not $v4JumpActive) -and (-not $v6JumpActive) -and $v4Actual.Count -eq 0 -and $v6Actual.Count -eq 0
        $state = if ($isRemoved) { "PASS" } else { "FAIL" }
        Write-Host "[$serial] validation (removed): $state"
    }
}

foreach ($serial in $Serials) {
    $deviceState = Get-DeviceState -Serial $serial
    if (-not $deviceState.IsOnline) {
        $stateLabel = if ([string]::IsNullOrWhiteSpace($deviceState.State)) { "unknown" } else { $deviceState.State }
        Write-Host "[$serial] skipped (device not online: state=$stateLabel, exitCode=$($deviceState.ExitCode))"
        continue
    }

    if ($Mode -ne "status") {
        $rootCheck = Ensure-RootAccess -Serial $serial
        if (-not $rootCheck.Success) {
            Write-Host "[$serial] refused ($($rootCheck.Message))"
            continue
        }
        Write-Host "[$serial] $($rootCheck.Message)"
    }
    else {
        $uidStatus = Invoke-AdbShell -Serial $serial -Cmd "id -u 2>/dev/null || echo UID_UNAVAILABLE"
        $uidLine = Join-FirstLine -Lines $uidStatus.Output
        if ($uidLine -eq "UID_UNAVAILABLE" -or [string]::IsNullOrWhiteSpace($uidLine)) {
            Write-Host "[$serial] status preflight: unable to determine shell uid (non-mutating mode)."
        }
        elseif ($uidLine -ne "0") {
            Write-Host "[$serial] status preflight: shell uid=$uidLine (non-root; status check remains non-mutating)."
        }
        else {
            Write-Host "[$serial] status preflight: shell uid=0."
        }
    }

    if ($Mode -eq "apply") {
        $applyV4 = Build-ApplyCommand -Tool "iptables" -Chain "C2_EGRESS_GUARD" -RuleSuffixes $SelectedProfile.IPv4Rules
        $applyV6 = Build-ApplyCommand -Tool "ip6tables" -Chain "C2_EGRESS_GUARD6" -RuleSuffixes $SelectedProfile.IPv6Rules
        Invoke-AdbShell -Serial $serial -Cmd $applyV4 | Out-Null
        Invoke-AdbShell -Serial $serial -Cmd $applyV6 | Out-Null
        Write-Host "[$serial] guard applied (profile=$Profile)"
        Write-Validation -Serial $serial -ProfileName $Profile -ProfileSpec $SelectedProfile -ExpectActive $true
    }
    elseif ($Mode -eq "remove") {
        Invoke-AdbShell -Serial $serial -Cmd "iptables -D OUTPUT -j C2_EGRESS_GUARD 2>/dev/null; iptables -F C2_EGRESS_GUARD 2>/dev/null; iptables -X C2_EGRESS_GUARD 2>/dev/null" | Out-Null
        Invoke-AdbShell -Serial $serial -Cmd "ip6tables -D OUTPUT -j C2_EGRESS_GUARD6 2>/dev/null; ip6tables -F C2_EGRESS_GUARD6 2>/dev/null; ip6tables -X C2_EGRESS_GUARD6 2>/dev/null" | Out-Null
        Write-Host "[$serial] guard removed"
        Write-Validation -Serial $serial -ProfileName $Profile -ProfileSpec $SelectedProfile -ExpectActive $false
    }
    else {
        Write-Validation -Serial $serial -ProfileName $Profile -ProfileSpec $SelectedProfile -ExpectActive $true
    }
}
