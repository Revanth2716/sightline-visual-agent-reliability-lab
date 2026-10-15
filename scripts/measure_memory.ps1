<#
.SYNOPSIS
    Sightline Phase 1 Reproducible Memory Measurement Script
.DESCRIPTION
    Measures Working Set and Private Bytes for:
    1) Root Python process
    2) Chromium child processes
    3) Complete process tree (Python + Playwright Driver + Chromium)
    across multiple repeatable trials executing all 5 scenarios.
#>

param(
    [int]$Trials = 3,
    [int]$SampleIntervalMs = 100
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir
$pythonExe = Join-Path $projectRoot ".venv\Scripts\python.exe"
$workloadScript = Join-Path $projectRoot "tests\workload_runner.py"

function Get-DescendantPids ($parentPid) {
    $pids = @()
    $children = Get-CimInstance Win32_Process -Filter "ParentProcessId = $parentPid" -ErrorAction SilentlyContinue
    foreach ($c in $children) {
        $pids += $c.ProcessId
        $pids += Get-DescendantPids $c.ProcessId
    }
    return $pids
}

$results = @()

Write-Host "============================================================"
Write-Host " SIGHTLINE PHASE 1 REPRODUCIBLE MEMORY MEASUREMENT"
Write-Host " Target: Python + Headless Chromium 5-Scenario Workload"
Write-Host " Trials: $Trials | Sample Interval: ${SampleIntervalMs}ms"
Write-Host "============================================================"

for ($t = 1; $t -le $Trials; $t++) {
    Write-Host "`n--- Running Trial $t of $Trials ---"
    
    # Check baseline chrome processes before trial
    $chromeBefore = @(Get-Process -Name "chrome" -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id)
    
    $proc = Start-Process -FilePath $pythonExe -ArgumentList "`"$workloadScript`"" -PassThru -NoNewWindow
    $rootPid = $proc.Id
    
    $peakPythonWS = 0
    $peakPythonPrivate = 0
    $peakChromiumWS = 0
    $peakChromiumPrivate = 0
    $peakTreeWS = 0
    $peakTreePrivate = 0
    $allObservedPids = [System.Collections.Generic.HashSet[int]]::new()
    $allObservedPids.Add($rootPid) | Out-Null
    
    while (-not $proc.HasExited) {
        $descendants = Get-DescendantPids $rootPid
        foreach ($d in $descendants) { $allObservedPids.Add($d) | Out-Null }
        
        $currentPids = @($rootPid) + $descendants
        
        $treeWS = 0
        $treePrivate = 0
        $chromiumInstantWS = 0
        $chromiumInstantPrivate = 0
        
        foreach ($pidToQuery in $currentPids) {
            $pObj = Get-Process -Id $pidToQuery -ErrorAction SilentlyContinue
            if ($pObj) {
                $ws = $pObj.WorkingSet64
                $priv = $pObj.PrivateMemorySize64
                $treeWS += $ws
                $treePrivate += $priv
                
                if ($pObj.Id -eq $rootPid) {
                    if ($ws -gt $peakPythonWS) { $peakPythonWS = $ws }
                    if ($priv -gt $peakPythonPrivate) { $peakPythonPrivate = $priv }
                }
                
                if ($pObj.ProcessName -like "*chrome*") {
                    $chromiumInstantWS += $ws
                    $chromiumInstantPrivate += $priv
                }
            }
        }
        
        if ($chromiumInstantWS -gt $peakChromiumWS) { $peakChromiumWS = $chromiumInstantWS }
        if ($chromiumInstantPrivate -gt $peakChromiumPrivate) { $peakChromiumPrivate = $chromiumInstantPrivate }
        if ($treeWS -gt $peakTreeWS) { $peakTreeWS = $treeWS }
        if ($treePrivate -gt $peakTreePrivate) { $peakTreePrivate = $treePrivate }
        
        Start-Sleep -Milliseconds $SampleIntervalMs
    }
    
    $exitCode = $proc.ExitCode
    Start-Sleep -Milliseconds 500  # Allow teardown settling
    
    # Check for lingering chrome processes that were spawned during this run
    $chromeAfter = @(Get-Process -Name "chrome" -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id)
    $lingeringPids = $chromeAfter | Where-Object { $allObservedPids.Contains($_) }
    
    $trialResult = [PSCustomObject]@{
        Trial = $t
        ExitCode = $exitCode
        RootPid = $rootPid
        ObservedPidsCount = $allObservedPids.Count
        PythonPeakWS_MB = [math]::Round($peakPythonWS / 1MB, 2)
        PythonPeakPriv_MB = [math]::Round($peakPythonPrivate / 1MB, 2)
        ChromiumPeakWS_MB = [math]::Round($peakChromiumWS / 1MB, 2)
        ChromiumPeakPriv_MB = [math]::Round($peakChromiumPrivate / 1MB, 2)
        TreePeakWS_MB = [math]::Round($peakTreeWS / 1MB, 2)
        TreePeakPriv_MB = [math]::Round($peakTreePrivate / 1MB, 2)
        LingeringChromiumProcesses = $lingeringPids.Count
    }
    
    $results += $trialResult
    Write-Host "Trial $t Result:"
    $trialResult | Format-List | Out-String | Write-Host
}

Write-Host "`n============================================================"
Write-Host " SUMMARY OVER ALL TRIALS"
Write-Host "============================================================"
$results | Format-Table Trial, ExitCode, PythonPeakWS_MB, ChromiumPeakWS_MB, TreePeakWS_MB, TreePeakPriv_MB, LingeringChromiumProcesses -AutoSize

# Export machine-readable JSON for audit report
$jsonOut = Join-Path $projectRoot "tests\memory_measurement_results.json"
$results | ConvertTo-Json -Depth 4 | Set-Content $jsonOut
Write-Host "Results saved to $jsonOut"
