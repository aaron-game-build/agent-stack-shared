<#
.SYNOPSIS
    Shared, config-driven Build-And-Launch pipeline for UE projects.
    Close UE Editor -> Build C++ -> Restart Editor -> run post-launch Python steps.

    This script is consumed via a thin project-root wrapper:
        & (Join-Path $PSScriptRoot "agent-stack-shared\scripts\Build-And-Launch.ps1") -ProjectRoot $PSScriptRoot @args

    All project-specific values (uproject name, engine root, build command, bridge path,
    discovery timeout, post-launch steps) come from the project's own .ue-py-config.json
    (toolchain / toolchain.build_launch / platforms.windows). This script has zero
    project-name placeholders.

.PARAMETER ProjectRoot
    Required. Absolute path to the consuming project's root (where .ue-py-config.json lives).

.PARAMETER SkipBuild
    Skip compile (use when C++ unchanged).

.PARAMETER SkipConfig
    Skip step 4 entirely (post-launch editor scripts + post checks).

.PARAMETER ForceKillEditor
    Last-resort fallback. If graceful shutdown fails, forcibly kill this project's
    UnrealEditor process(es) only. This can trigger the UE recovery/autosave dialog on the
    next launch.

.PARAMETER EngineRoot
    Override the engine root. Default: platforms.windows.engine_root from .ue-py-config.json.

.PARAMETER DryRun
    Parse config and print every step that would run, without doing anything. Exits 0.
    Missing required config keys are still reported as errors.

.EXAMPLE
    & Build-And-Launch.ps1 -ProjectRoot "G:\UEProjects\Oathboard"
    & Build-And-Launch.ps1 -ProjectRoot "G:\UEProjects\Oathboard" -SkipBuild
    & Build-And-Launch.ps1 -ProjectRoot "G:\UEProjects\Oathboard" -DryRun
#>
param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectRoot,
    [switch]$SkipBuild,
    [switch]$SkipConfig,
    [switch]$ForceKillEditor,
    [string]$EngineRoot,
    [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Get-RequiredConfigValue {
    param(
        [Parameter(Mandatory = $true)]$Config,
        [Parameter(Mandatory = $true)][string]$DottedPath
    )
    $node = $Config
    $parts = $DottedPath -split '\.'
    foreach ($part in $parts) {
        if ($null -eq $node) {
            throw "Missing required .ue-py-config.json key: $DottedPath"
        }
        $node = $node.$part
        if ($null -eq $node) {
            throw "Missing required .ue-py-config.json key: $DottedPath"
        }
    }
    return $node
}

function Get-OptionalConfigValue {
    param(
        [Parameter(Mandatory = $true)]$Config,
        [Parameter(Mandatory = $true)][string]$DottedPath,
        $Default = $null
    )
    $node = $Config
    $parts = $DottedPath -split '\.'
    foreach ($part in $parts) {
        if ($null -eq $node) { return $Default }
        $node = $node.$part
    }
    if ($null -eq $node) { return $Default }
    return $node
}

function Invoke-BuildCommandLine {
    param([Parameter(Mandatory = $true)][string]$CommandLine)
    if ($CommandLine -match '^"([^"]+)"\s+(.*)$') {
        $exe = $matches[1]
        $argString = $matches[2]
    } elseif ($CommandLine -match '^(\S+)\s+(.*)$') {
        $exe = $matches[1]
        $argString = $matches[2]
    } else {
        throw "Invalid build_command: $CommandLine"
    }
    return Start-Process -FilePath $exe -ArgumentList $argString -NoNewWindow -Wait -PassThru
}

function Get-ProjectEditorProcesses {
    # Only return UnrealEditor.exe processes whose command line references this project's
    # .uproject file name. Never fall back to "all UnrealEditor processes" -- another
    # project's editor may be running on the same machine.
    param([Parameter(Mandatory = $true)][string]$UprojectFileName)

    $matched = @()
    try {
        $cimProcs = Get-CimInstance Win32_Process -Filter "Name='UnrealEditor.exe'" -ErrorAction Stop
    } catch {
        Write-Host "[WARN] Could not query running UnrealEditor.exe processes via CIM ($($_.Exception.Message)). Assuming none are running for this project."
        return @()
    }

    foreach ($cimProc in $cimProcs) {
        $cmdLine = $cimProc.CommandLine
        if ($cmdLine -and ($cmdLine -match [regex]::Escape($UprojectFileName))) {
            try {
                $proc = Get-Process -Id $cimProc.ProcessId -ErrorAction Stop
                $matched += $proc
            } catch {
                # Process may have exited between the CIM query and Get-Process; ignore.
            }
        }
    }
    return $matched
}

function Wait-ProjectEditorExit {
    param(
        [Parameter(Mandatory = $true)][string]$UprojectFileName,
        [int]$TimeoutSeconds = 30
    )
    $elapsed = 0
    while ((Get-ProjectEditorProcesses -UprojectFileName $UprojectFileName).Count -gt 0 -and $elapsed -lt $TimeoutSeconds) {
        Start-Sleep -Seconds 1
        $elapsed++
    }
    return ((Get-ProjectEditorProcesses -UprojectFileName $UprojectFileName).Count -eq 0)
}

# ---------------------------------------------------------------------------
# Load config
# ---------------------------------------------------------------------------
$ConfigPath = Join-Path $ProjectRoot ".ue-py-config.json"
if (-not (Test-Path $ConfigPath)) {
    Write-Host "[ERR] .ue-py-config.json not found at $ConfigPath"
    exit 1
}
$Config = Get-Content $ConfigPath -Encoding UTF8 | ConvertFrom-Json

try {
    $Platform      = Get-RequiredConfigValue -Config $Config -DottedPath "platforms.windows"
    $BuildLaunch   = Get-RequiredConfigValue -Config $Config -DottedPath "toolchain.build_launch"
    $UprojectName  = Get-RequiredConfigValue -Config $Config -DottedPath "toolchain.build_launch.uproject"
    $BuildCommand  = Get-RequiredConfigValue -Config $Config -DottedPath "platforms.windows.build_command"
    $UePyRelPath   = Get-RequiredConfigValue -Config $Config -DottedPath "ue_python_script"
} catch {
    Write-Host "[ERR] $($_.Exception.Message)"
    exit 1
}

if (-not $EngineRoot) {
    if (-not $Platform.engine_root) {
        Write-Host "[ERR] Missing required .ue-py-config.json key: platforms.windows.engine_root (or pass -EngineRoot)"
        exit 1
    }
    $EngineRoot = $Platform.engine_root -replace '/', '\'
    $EngineRoot = $EngineRoot -replace '\\Engine$', ''
}

$Toolchain = $Config.toolchain
$ReadinessToken     = Get-OptionalConfigValue -Config $Config -DottedPath "toolchain.readiness_token" -Default "UE_REMOTE_OK"
$ReadinessPing      = Get-OptionalConfigValue -Config $Config -DottedPath "toolchain.readiness_ping" -Default "import unreal; print('$ReadinessToken')"
$MaxWait            = [int](Get-OptionalConfigValue -Config $Config -DottedPath "toolchain.remote_exec_max_wait_seconds" -Default 180)
$PollInterval       = [int](Get-OptionalConfigValue -Config $Config -DottedPath "toolchain.remote_exec_poll_interval_seconds" -Default 10)
$DiscoveryTimeout   = [int](Get-OptionalConfigValue -Config $Config -DottedPath "toolchain.remote_exec_discovery_timeout_seconds" -Default 20)

$PostLaunchEditorScripts = @(Get-OptionalConfigValue -Config $Config -DottedPath "toolchain.build_launch.post_launch_editor_scripts" -Default @())
$PostChecks              = @(Get-OptionalConfigValue -Config $Config -DottedPath "toolchain.build_launch.post_checks" -Default @())

$EngineRootForExe = Join-Path $EngineRoot "Engine"
if (Test-Path (Join-Path $EngineRoot "Binaries\Win64\UnrealEditor.exe")) {
    # engine_root already points at the Engine/ dir itself
    $EngineRootForExe = $EngineRoot
}
$EditorExe   = Join-Path $EngineRootForExe "Binaries\Win64\UnrealEditor.exe"
$ProjectFile = Join-Path $ProjectRoot $UprojectName

$UePyBridge = Join-Path $ProjectRoot ($UePyRelPath -replace '/', '\')

# ---------------------------------------------------------------------------
# DryRun: print the plan and exit
# ---------------------------------------------------------------------------
if ($DryRun) {
    Write-Host ""
    Write-Host "=== Build-And-Launch DryRun ==="
    Write-Host "  Project root      : $ProjectRoot"
    Write-Host "  Uproject          : $ProjectFile"
    Write-Host "  Engine root       : $EngineRootForExe"
    Write-Host "  Editor exe        : $EditorExe"
    Write-Host "  Build command     : $BuildCommand"
    Write-Host "  ue_python bridge  : $UePyBridge"
    Write-Host "  Discovery timeout : ${DiscoveryTimeout}s"
    Write-Host "  Readiness token   : $ReadinessToken"
    Write-Host "  Readiness ping    : $ReadinessPing"
    Write-Host "  Max wait / poll   : ${MaxWait}s / ${PollInterval}s"
    Write-Host "  SkipBuild         : $($SkipBuild.IsPresent)"
    Write-Host "  SkipConfig        : $($SkipConfig.IsPresent)"
    Write-Host "  ForceKillEditor   : $($ForceKillEditor.IsPresent)"
    Write-Host ""
    Write-Host "  Step 1: close editor instances matching '$UprojectName' in command line"
    Write-Host "  Step 2: $(if ($SkipBuild) { '(skipped, -SkipBuild)' } else { $BuildCommand })"
    Write-Host "  Step 3: Start-Process $EditorExe `"$ProjectFile`""
    if ($SkipConfig) {
        Write-Host "  Step 4: (skipped, -SkipConfig)"
    } else {
        Write-Host "  Step 4a: wait for Remote Execution (token=$ReadinessToken, timeout=${MaxWait}s)"
        Write-Host "  Step 4b: post_launch_editor_scripts (mode=editor, via bridge -f):"
        if ($PostLaunchEditorScripts.Count -eq 0) {
            Write-Host "    (none configured)"
        } else {
            foreach ($rel in $PostLaunchEditorScripts) {
                Write-Host "    - $rel"
            }
        }
        Write-Host "  Step 4c: post_checks:"
        if ($PostChecks.Count -eq 0) {
            Write-Host "    (none configured)"
        } else {
            foreach ($check in $PostChecks) {
                Write-Host "    - $($check.script)  [mode=$($check.mode)]"
            }
        }
    }
    Write-Host ""
    Write-Host "=== DryRun complete (no actions taken) ==="
    exit 0
}

# ---------------------------------------------------------------------------
# Real run
# ---------------------------------------------------------------------------
if (-not (Test-Path $UePyBridge)) {
    Write-Host "[ERR] ue_python.py not found at $UePyBridge (see .ue-py-config.json ue_python_script)"
    exit 1
}

Write-Host ""
Write-Host "=== Build-And-Launch ==="
Write-Host "  Engine : $EngineRootForExe"
Write-Host "  Project: $ProjectFile"
Write-Host ""

# Step 1: Close this project's UE Editor instance(s) only
$editorProcs = Get-ProjectEditorProcesses -UprojectFileName $UprojectName
if ($editorProcs.Count -gt 0) {
    Write-Host "[1/4] Closing UnrealEditor gracefully (project: $UprojectName)..."

    $remoteQuitSent = $false
    try {
        $quitResult = & python $UePyBridge "import unreal; unreal.SystemLibrary.quit_editor()" $DiscoveryTimeout 2>&1
        if ($LASTEXITCODE -eq 0) {
            $remoteQuitSent = $true
            Write-Host "  Sent Remote Execution quit request."
        } elseif ($quitResult) {
            Write-Host "  Remote quit unavailable, fallback to window close."
        }
    } catch {
        Write-Host "  Remote quit unavailable, fallback to window close."
    }

    foreach ($proc in (Get-ProjectEditorProcesses -UprojectFileName $UprojectName)) {
        if ($proc.MainWindowHandle -ne 0) {
            [void]$proc.CloseMainWindow()
        }
    }

    $closedGracefully = Wait-ProjectEditorExit -UprojectFileName $UprojectName -TimeoutSeconds 30
    if (-not $closedGracefully -and $ForceKillEditor) {
        Write-Host "[WARN] Editor did not exit gracefully within 30s; forcing shutdown of this project's instance(s) because -ForceKillEditor was provided."
        Get-ProjectEditorProcesses -UprojectFileName $UprojectName | Stop-Process -Force
        $closedGracefully = Wait-ProjectEditorExit -UprojectFileName $UprojectName -TimeoutSeconds 10
    }

    if (-not $closedGracefully) {
        Write-Host "[ERR] Editor did not exit cleanly within 30s. Aborting launch to avoid autosave recovery dialogs. Close Unreal Editor manually or rerun with -ForceKillEditor if you accept recovery-risk shutdown."
        exit 1
    } else {
        if ($remoteQuitSent) {
            Write-Host "  Editor closed cleanly via quit request."
        } else {
            Write-Host "  Editor closed cleanly."
        }
    }
} else {
    Write-Host "[1/4] Editor not running for this project, skip close"
}

Start-Sleep -Seconds 1

# Step 2: Build C++
if ($SkipBuild) {
    Write-Host "[2/4] -SkipBuild, skip compile"
} else {
    Write-Host "[2/4] Building (Development/Win64)..."
    Write-Host "  Using: $BuildCommand"
    Write-Host ""

    $buildProc = Invoke-BuildCommandLine -CommandLine $BuildCommand
    $buildExitCode = $buildProc.ExitCode

    if ($buildExitCode -ne 0) {
        Write-Host ""
        Write-Host "[ERR] Build failed. Exit code: $buildExitCode. Check output above."
        exit $buildExitCode
    }

    Write-Host ""
    Write-Host "[OK] Build succeeded."
}

# Step 3: Launch UE Editor
Write-Host "[3/4] Starting UnrealEditor..."
Write-Host "  $EditorExe `"$ProjectFile`""

Start-Process -FilePath $EditorExe -ArgumentList "`"$ProjectFile`""

if ($SkipConfig) {
    Write-Host ""
    Write-Host "  -SkipConfig, not waiting for Remote Execution."
    Write-Host "=== Done (build + launch) ==="
    exit 0
}

# Step 4: Wait for Remote Execution, then run post-launch editor scripts + post checks
Write-Host "[4/4] Waiting for Editor Remote Execution..."
Write-Host "  (First cold start often takes 60-120s; token: $ReadinessToken)"

$env:UE_ENGINE_ROOT = $EngineRootForExe
$env:PYTHONIOENCODING = "utf-8"

$elapsed = 0
$ready = $false

while ($elapsed -lt $MaxWait) {
    Start-Sleep -Seconds $PollInterval
    $elapsed += $PollInterval

    $pingExit = 0
    $pingResult = $null
    try {
        $pingResult = & python $UePyBridge $ReadinessPing $DiscoveryTimeout 2>&1
        $pingExit = $LASTEXITCODE
    } catch {
        $pingExit = 2
    }

    if ($pingExit -eq 0 -and ($pingResult -match $ReadinessToken)) {
        $ready = $true
        Write-Host "[OK] Editor ready (waited ${elapsed}s)"
        break
    }
    Write-Host "  ... still waiting (${elapsed}s / ${MaxWait}s)"
}

if (-not $ready) {
    Write-Host "[MANUAL] Editor did not respond to Remote Execution within ${MaxWait}s."
    Write-Host "[MANUAL] Enable: Project Settings -> Plugins -> Python -> Remote Execution"
    Write-Host "[MANUAL] Editor is running. Run the project's config workflow manually when ready."
    exit 1
}

foreach ($rel in $PostLaunchEditorScripts) {
    $scriptPath = Join-Path $ProjectRoot ($rel -replace '/', '\')
    Write-Host ""
    Write-Host "  Running post-launch editor script: $scriptPath"
    & python $UePyBridge -f $scriptPath $DiscoveryTimeout

    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERR] $rel returned an error. Check output above."
        exit $LASTEXITCODE
    }
}

foreach ($check in $PostChecks) {
    $checkScriptRel = $check.script
    $checkMode = $check.mode
    $checkScriptPath = Join-Path $ProjectRoot ($checkScriptRel -replace '/', '\')

    if ($checkMode -eq 'local') {
        Write-Host ""
        Write-Host "  Running post check (local): $checkScriptPath"
        & python $checkScriptPath
        $checkExitCode = $LASTEXITCODE
    } elseif ($checkMode -eq 'editor') {
        Write-Host ""
        Write-Host "  Running post check (editor): $checkScriptPath"
        & python $UePyBridge -f $checkScriptPath $DiscoveryTimeout
        $checkExitCode = $LASTEXITCODE
    } else {
        Write-Host "[ERR] Unknown post_checks mode '$checkMode' for $checkScriptRel (expected 'local' or 'editor')"
        exit 1
    }

    if ($checkExitCode -ne 0) {
        Write-Host "[ERR] $checkScriptRel failed (post_checks gate, mode=$checkMode). Check output above."
        exit $checkExitCode
    }
}

Write-Host ""
Write-Host "[OK] All done."
