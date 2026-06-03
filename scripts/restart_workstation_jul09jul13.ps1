# Restart o run Workstation Jul 6-13 a partir do rst @ Jul 9 00:00.
#
# Contexto: o run cold-start Jul 6 -> Jul 13 (com uxuy preservado) rodou 4 dias
# limpos e crashou em Jul 10 00:05 com EOF de turbid_airport/saltpans_discharge.bc.
# Os 2 .bc já foram estendidos localmente até Jul 13 (linha "17280  0.0") e
# precisam ser copiados para a Workstation antes de rodar este script.
#
# Uso (na Workstation, PowerShell):
#   cd C:\Users\...\StagnoneDT
#   .\scripts\restart_workstation_jul09jul13.ps1
#
# (Se PowerShell bloquear execução: `powershell -ExecutionPolicy Bypass -File scripts/restart_workstation_jul09jul13.ps1`)
#
# O script NÃO lança a simulação — só prepara o restart. Verifique a saída e
# depois rode manualmente run_dimr_parallel.bat.

$ErrorActionPreference = 'Stop'

# === Config ===
$Root = if ($env:STAGNONE_ROOT) { $env:STAGNONE_ROOT } else { (Resolve-Path "$PSScriptRoot\..").Path }
$Model = Join-Path $Root 'model\dflowfm_v04AE_jul06jul13'
$DfmOut = Join-Path $Model 'DFM_OUTPUT_Stagnone_dxy01_15m'
$RstDate = '20250709'
$RstDatetime = "${RstDate}_000000"

$TStopNew = '345600.0'      # 4 days * 86400 s
$StartNew = '20250709000000'
$StopNew  = '20250713000000'

# === Verificações ===
if (-not (Test-Path $Model)) {
    throw "ERROR: model dir not found: $Model"
}
if (-not (Test-Path $DfmOut)) {
    throw "ERROR: DFM_OUTPUT not found: $DfmOut"
}

# 8 rst @ Jul 9 existem?
$RstFiles = Get-ChildItem -Path $DfmOut -Filter "Stagnone_dxy01_15m_*_${RstDatetime}_rst.nc"
if ($RstFiles.Count -ne 8) {
    Write-Host "ERROR: expected 8 rst @ Jul 9 in $DfmOut, found $($RstFiles.Count)"
    Write-Host 'Available rst files:'
    Get-ChildItem -Path $DfmOut -Filter "Stagnone_dxy01_15m_*_rst.nc" | ForEach-Object {
        Write-Host "  $($_.Name)"
    }
    throw 'Missing Jul 9 rst files'
}
Write-Host "[1/6] 8 rst @ Jul 9 00:00 confirmados em $DfmOut"

# Turbid .bc estendidos (linha 17280)?
foreach ($bc in @('turbid_airport_discharge.bc', 'turbid_saltpans_discharge.bc')) {
    $bcPath = Join-Path $Model $bc
    if (-not (Test-Path $bcPath)) {
        throw "ERROR: $bcPath not found"
    }
    $content = Get-Content $bcPath
    if (-not ($content | Select-String -Pattern '^17280\s')) {
        Write-Host "ERROR: $bc nao tem a linha 17280 (precisa ser patcheado antes)"
        Write-Host '  Ultimas 3 linhas:'
        $content | Select-Object -Last 3 | ForEach-Object { Write-Host "    $_" }
        throw "$bc not patched"
    }
}
Write-Host '[2/6] turbid .bc files extendidos para 17280 min (Jul 13 00:00)'

# uxuy.bc estendido (ultimo timestep >= 277920 = Jul 13 00:00 em minutes since 2025-01-01)?
$uxuyBc = Join-Path $Model 'uxuyadvectionvelocitybnd_CMEMS_Stagnone_dxy01_15m.bc'
if (Test-Path $uxuyBc) {
    $uxuyTail = Get-Content $uxuyBc | Select-Object -Last 200 | Where-Object { $_ -match '^[0-9]+\.' }
    if ($uxuyTail.Count -gt 0) {
        $lastTime = [double]((($uxuyTail | Select-Object -Last 1) -split '\s+')[0])
        if ($lastTime -lt 277920) {
            Write-Host "ERROR: uxuy.bc termina em $lastTime min (precisa >= 277920 = Jul 13 00:00)"
            Write-Host '       Substituir por uxuyadvectionvelocitybnd_CMEMS_Stagnone_dxy01_15m.bc estendido'
            Write-Host '       (gerado pelo build_uxuy_bc_v04AE_d10d12_extended.py no laptop).'
            throw 'uxuy.bc too short'
        }
    }
}
Write-Host '[2b/6] uxuy.bc cobre ate Jul 13 (timestamp final OK)'

# === Backup DFM_OUTPUT atual ===
$Stamp = (Get-Date -Format 'yyyyMMddTHHmmssZ')
$Backup = "$DfmOut.jul06_to_jul10_eof_$Stamp"
Move-Item -Path $DfmOut -Destination $Backup
New-Item -Path $DfmOut -ItemType Directory | Out-Null
Write-Host "[3/6] DFM_OUTPUT antigo movido para: $Backup"

# === Copiar rst @ Jul 9 para restart_input ===
$RestartInput = Join-Path $Model 'restart_input'
if (-not (Test-Path $RestartInput)) {
    New-Item -Path $RestartInput -ItemType Directory | Out-Null
}
foreach ($n in 0..7) {
    $rank = '{0:D4}' -f $n
    $src = Join-Path $Backup "Stagnone_dxy01_15m_${rank}_${RstDatetime}_rst.nc"
    Copy-Item -Path $src -Destination $RestartInput
}
Write-Host "[4/6] 8 rst files copiados para $RestartInput"

# === Patch MDUs (master + 8 partição se existirem) ===
function Patch-Mdu {
    param(
        [string]$Path,
        [string]$Rank   # '' para master, ou 'NNNN'
    )
    if (-not (Test-Path $Path)) {
        Write-Host "  [skip] $Path not found"
        return
    }
    Copy-Item -Path $Path -Destination "$Path.bak.pre_restart"

    # Lê em string única pra preservar newlines originais com -Raw
    $text = Get-Content $Path -Raw

    if ($Rank -eq '') {
        $rstFile = "restart_input/Stagnone_dxy01_15m_0000_${RstDatetime}_rst.nc"
    } else {
        $rstFile = "restart_input/Stagnone_dxy01_15m_${Rank}_${RstDatetime}_rst.nc"
    }

    $text = $text -replace '(?m)^tStart\s*=.*',          "tStart                  = 0.0            # Restart from Jul 9 (was cold-start Jul 6)"
    $text = $text -replace '(?m)^tStop\s*=.*',           "tStop                   = $TStopNew        # 4 days Jul 9 -> Jul 13"
    $text = $text -replace '(?m)^startDateTime\s*=.*',   "startDateTime           = $StartNew # Restart from Jul 9 00:00"
    $text = $text -replace '(?m)^stopDateTime\s*=.*',    "stopDateTime            = $StopNew # Jul 13 00:00 unchanged"
    $text = $text -replace '(?m)^restartFile\s*=.*',     "restartFile     = $rstFile"
    $text = $text -replace '(?m)^restartDateTime\s*=.*', "restartDateTime = $StartNew"

    # Set-Content em UTF-16 LE BOM por default no PS 5.1 — usar ASCII pra preservar
    # encoding original da MDU sem alterar parsers downstream.
    Set-Content -Path $Path -Value $text -Encoding ASCII -NoNewline
}

# Master
Patch-Mdu -Path (Join-Path $Model 'Stagnone_dxy01_15m.mdu') -Rank ''

# Partições (se já existem de partition prévio)
foreach ($n in 0..7) {
    $rank = '{0:D4}' -f $n
    Patch-Mdu -Path (Join-Path $Model "Stagnone_dxy01_15m_${rank}.mdu") -Rank $rank
}
Write-Host '[5/6] MDUs patcheados (master + particoes onde existem)'
Write-Host '      Verificar master:'
Select-String -Path (Join-Path $Model 'Stagnone_dxy01_15m.mdu') -Pattern '^(tStart|tStop|startDateTime|stopDateTime|restartFile|restartDateTime)' | ForEach-Object {
    Write-Host "        $($_.Line)"
}

# === Caches ===
Get-ChildItem -Path $Model -Filter '*.cache' -ErrorAction SilentlyContinue | Remove-Item -Force
Write-Host '[6/7] caches removidos'

# === Gerar run_restart.bat (launcher dimr-only, pula re-partition) ===
$partExist = Test-Path (Join-Path $Model 'Stagnone_dxy01_15m_0000.mdu')
$runRestartBat = Join-Path $Model 'run_restart.bat'
$batContent = @'
@echo off
rem ============================================================
rem Stagnone Jul 9->13 RESTART launcher (gerado por
rem scripts/restart_workstation_jul09jul13.ps1).
rem
rem NAO re-particiona: as particoes _0000.mdu..._0007.mdu ja
rem estao patcheadas com restartFile/startDateTime/etc.
rem Re-particionar destruiria esses patches.
rem
rem PREFLIGHT: chama scripts/check_bc_coverage.ps1 antes de
rem lancar. Se qualquer .bc/.nc nao cobrir a janela, EXIT
rem nao-zero e nao lanca o dimr. Pegou o uxuy EOF que crashou
rem o run anterior em Jul 10 12:00.
rem ============================================================

cd /d "%~dp0"

set dimrset=C:\Program Files\Deltares\Delft3D FM Suite 2026.01 HMWQ\plugins\DeltaShell.Dimr\kernels\x64
set nPart=8

rem ----- SWAN OpenMP throttle (mesmo do run_model.bat original) -----
set KMP_HW_SUBSET=16c,1t
set OMP_NUM_THREADS=16
set MKL_NUM_THREADS=16

set "PATH=%dimrset%\bin;%dimrset%\lib;%dimrset%\share\bin;%PATH%"

echo ============================================================
echo Stagnone Jul 9-13 RESTART run (%nPart% MPI processes)
echo Working directory: %CD%
echo ============================================================
echo.

rem ----- Preflight (PowerShell, strict) -----
set PREFLIGHT=%~dp0..\..\scripts\check_bc_coverage.ps1
if not exist "%PREFLIGHT%" (
    echo PREFLIGHT NAO ENCONTRADO em %PREFLIGHT%.
    echo Copie scripts\check_bc_coverage.ps1 antes de relancar.
    pause
    exit /b 10
)
powershell -ExecutionPolicy Bypass -File "%PREFLIGHT%" "%CD%"
if errorlevel 1 (
    echo.
    echo PREFLIGHT FAILED - veja saida acima. Aborting launch.
    pause
    exit /b 11
)
echo Preflight passed. Launching dimr...
echo.

call "%dimrset%\bin\run_dimr_parallel.bat" %nPart% dimr_config.xml

echo.
echo ============================================================
echo Restart run finished with exit code: %ERRORLEVEL%
echo ============================================================
pause
'@
Set-Content -Path $runRestartBat -Value $batContent -Encoding ASCII
Write-Host "[7/7] gerado launcher (com preflight): $runRestartBat"

# === Proximos passos manuais ===
Write-Host ''
Write-Host '============================================================'
Write-Host 'PRONTO. Proximos passos manuais na Workstation:'
Write-Host ''
if ($partExist) {
    Write-Host '1. Particoes _0000.mdu..._0007.mdu ja existem com restartFile patcheado.'
    Write-Host '   Lancar diretamente o restart:'
    Write-Host "     cd $Model"
    Write-Host '     run_restart.bat'
    Write-Host '   (ou duplo-clique no run_restart.bat)'
} else {
    Write-Host 'AVISO: nao ha particoes _0000.mdu..._0007.mdu no model dir.'
    Write-Host 'O run anterior deve ter ja particionado; verificar se foram deletadas.'
    Write-Host 'Se precisar re-particionar primeiro:'
    Write-Host "     cd $Model"
    Write-Host '     "C:\Program Files\Deltares\Delft3D FM Suite 2026.01 HMWQ\plugins\DeltaShell.Dimr\kernels\x64\bin\run_dflowfm.bat" --partition:ndomains=8:icgsolver=6 Stagnone_dxy01_15m.mdu'
    Write-Host '   ATENCAO: re-particionar regenera _0000.mdu..._0007.mdu a partir do master,'
    Write-Host '   entao os patches de restart serao preservados (master ja foi patcheado).'
    Write-Host '   Depois rodar: run_restart.bat'
}
Write-Host ''
Write-Host '2. Wall time esperado: ~2h para 4 dias coupled em 8 MPI.'
Write-Host ''
Write-Host "3. Output Jul 9-13 ficara em $DfmOut (limpo)."
Write-Host "   Output Jul 6-10 original em $Backup."
Write-Host '============================================================'
