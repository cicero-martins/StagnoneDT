# Preflight estrito: verifica que TODOS os .bc + .nc referenciados pelos
# .ext do model dir cobrem a janela completa do MDU (startDateTime ->
# stopDateTime). EXIT NON-ZERO se qualquer arquivo falhar coverage.
#
# Uso: powershell -ExecutionPolicy Bypass -File scripts\check_bc_coverage.ps1 <model_dir>
#
# Diseñado para ser chamado de dentro de run_restart.bat / run_model.bat para
# travar o launch quando uma .bc termina antes da janela (gotcha que pegou tanto
# o Workstation Jul 6-13 quanto o simit chain Jul 11).

$ErrorActionPreference = 'Stop'

if ($args.Count -lt 1) {
    Write-Error 'Usage: check_bc_coverage.ps1 <model_dir>'
    exit 1
}
$ModelDir = $args[0]
if (-not (Test-Path $ModelDir -PathType Container)) {
    Write-Error "Model dir not found: $ModelDir"
    exit 2
}

# Master MDU (no _NNNN suffix)
$mduFiles = Get-ChildItem -Path $ModelDir -Filter 'Stagnone_*.mdu' |
    Where-Object { $_.Name -notmatch '_\d{4}\.mdu$' }
if ($mduFiles.Count -eq 0) {
    Write-Error "No master MDU found in $ModelDir"
    exit 3
}
$mdu = $mduFiles[0]

# Extract window
function Get-MduKey($file, $key) {
    $line = Get-Content $file.FullName | Where-Object { $_ -match "^\s*$key\s*=" } | Select-Object -First 1
    if (-not $line) { return $null }
    ($line -split '=', 2)[1].Trim() -split '\s+' | Select-Object -First 1
}
$startStr = Get-MduKey $mdu 'startDateTime'
$stopStr  = Get-MduKey $mdu 'stopDateTime'
if (-not $startStr -or -not $stopStr) {
    Write-Error "Missing startDateTime/stopDateTime in $($mdu.Name)"
    exit 3
}

function Parse-Yyyymmddhhmmss($s) {
    [datetime]::ParseExact($s.Substring(0, 14), 'yyyyMMddHHmmss', [Globalization.CultureInfo]::InvariantCulture, [Globalization.DateTimeStyles]::AssumeUniversal -bor [Globalization.DateTimeStyles]::AdjustToUniversal)
}
$winStart = Parse-Yyyymmddhhmmss $startStr
$winStop  = Parse-Yyyymmddhhmmss $stopStr

Write-Host '==================================================================='
Write-Host ' BC + Forcings coverage check (PowerShell preflight)'
Write-Host " Model dir : $ModelDir"
Write-Host " MDU       : $($mdu.Name)"
Write-Host (' Window    : {0} -> {1}' -f $winStart.ToString('yyyy-MM-dd HH:mm'), $winStop.ToString('yyyy-MM-dd HH:mm'))
Write-Host '==================================================================='

# Parse "minutes since 2025-07-01 00:00:00" -> ref UTC + multiplier seconds-per-unit
function Parse-TimeUnit($unit) {
    if (-not $unit) { return $null }
    $mult = switch -Regex ($unit) {
        '^minutes' { 60.0 }
        '^hours'   { 3600.0 }
        '^seconds' { 1.0 }
        '^days'    { 86400.0 }
        default    { 60.0 }
    }
    if ($unit -match 'since\s+(\d{4}-\d{2}-\d{2}(?:[T\s]\d{2}:\d{2}:\d{2})?)') {
        $ds = $matches[1] -replace 'T', ' '
        if ($ds -notmatch '\d{2}:\d{2}:\d{2}') { $ds = "$ds 00:00:00" }
        $ref = [datetime]::ParseExact($ds, 'yyyy-MM-dd HH:mm:ss', [Globalization.CultureInfo]::InvariantCulture, [Globalization.DateTimeStyles]::AssumeUniversal -bor [Globalization.DateTimeStyles]::AdjustToUniversal)
        return @{ Ref = $ref; Mult = $mult }
    }
    return $null
}

function Check-Bc($path) {
    if (-not (Test-Path $path)) {
        return @{ Status = 'MISSING'; FirstIso = '-'; LastIso = '-' }
    }
    $lines = Get-Content $path
    # First "since"-style unit line
    $unitLine = $lines | Where-Object { $_ -match 'unit\s*=' -and $_ -match 'since' } | Select-Object -First 1
    if (-not $unitLine) {
        return @{ Status = 'NO_TIME_UNIT'; FirstIso = '-'; LastIso = '-' }
    }
    $unit = ($unitLine -split '=', 2)[1].Trim()
    $tu = Parse-TimeUnit $unit
    if (-not $tu) {
        return @{ Status = 'BAD_UNIT'; FirstIso = '-'; LastIso = '-' }
    }
    # First/last numeric time in first [Forcing] block (assume all blocks share range)
    $inFirst = $false; $count = 0
    $firstT = $null; $lastT = $null
    foreach ($ln in $lines) {
        if ($ln -match '^\[Forcing\]') {
            $count++
            if ($count -gt 1) { break }
            $inFirst = $true
            continue
        }
        if ($inFirst -and $ln -match '^[\s]*[0-9]') {
            $tok = ($ln -split '\s+', 2)[0].Trim()
            if ([double]::TryParse($tok, [ref]$null)) {
                if (-not $firstT) { $firstT = [double]$tok }
                $lastT = [double]$tok
            }
        }
    }
    if (-not $firstT) {
        return @{ Status = 'EMPTY'; FirstIso = '-'; LastIso = '-' }
    }
    $first = $tu.Ref.AddSeconds($firstT * $tu.Mult)
    $last  = $tu.Ref.AddSeconds($lastT  * $tu.Mult)
    $status = 'OK'
    if ($first -gt $winStart) { $status = 'LATE_START' }
    if ($last  -lt $winStop)  { $status = 'EARLY_END' }
    return @{ Status = $status; FirstIso = $first.ToString('yyyy-MM-dd HH:mm'); LastIso = $last.ToString('yyyy-MM-dd HH:mm') }
}

function Check-Nc($path) {
    if (-not (Test-Path $path)) {
        return @{ Status = 'MISSING'; FirstIso = '-'; LastIso = '-' }
    }
    # Tenta ncdump (Delft FM Suite traz ncdump no PATH se setado)
    $ncdump = Get-Command ncdump -ErrorAction SilentlyContinue
    if (-not $ncdump) {
        return @{ Status = 'NO_NCDUMP_SKIP'; FirstIso = '-'; LastIso = '-' }
    }
    $hdr = & ncdump -h $path 2>$null
    if (-not $hdr) {
        return @{ Status = 'NCDUMP_ERR'; FirstIso = '-'; LastIso = '-' }
    }
    $timevar = $null
    foreach ($tv in @('time', 'TIME', 'valid_time')) {
        if ($hdr -match "\s$tv\([^)]*\)") {
            $timevar = $tv; break
        }
    }
    if (-not $timevar) {
        return @{ Status = 'NO_TIMEVAR'; FirstIso = '-'; LastIso = '-' }
    }
    $unit = $null
    foreach ($ln in $hdr) {
        if ($ln -match "${timevar}:units\s*=\s*`"([^`"]+)`"") {
            $unit = $matches[1]; break
        }
    }
    if (-not $unit) {
        return @{ Status = 'NO_UNIT'; FirstIso = '-'; LastIso = '-' }
    }
    $tu = Parse-TimeUnit $unit
    if (-not $tu) {
        return @{ Status = 'BAD_UNIT'; FirstIso = '-'; LastIso = '-' }
    }
    $vals = & ncdump -v $timevar $path 2>$null
    if (-not $vals) {
        return @{ Status = 'EMPTY'; FirstIso = '-'; LastIso = '-' }
    }
    # Encontrar bloco "data:\n <time> = ..., ;"
    $joined = ($vals -join "`n")
    if ($joined -match "(?ms)$timevar\s*=\s*([^;]+);") {
        $tokens = [regex]::Matches($matches[1], '[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?')
        if ($tokens.Count -eq 0) {
            return @{ Status = 'EMPTY'; FirstIso = '-'; LastIso = '-' }
        }
        $firstT = [double]$tokens[0].Value
        $lastT  = [double]$tokens[$tokens.Count - 1].Value
        $first = $tu.Ref.AddSeconds($firstT * $tu.Mult)
        $last  = $tu.Ref.AddSeconds($lastT  * $tu.Mult)
        $status = 'OK'
        if ($first -gt $winStart) { $status = 'LATE_START' }
        if ($last  -lt $winStop)  { $status = 'EARLY_END' }
        return @{ Status = $status; FirstIso = $first.ToString('yyyy-MM-dd HH:mm'); LastIso = $last.ToString('yyyy-MM-dd HH:mm') }
    }
    return @{ Status = 'PARSE_FAIL'; FirstIso = '-'; LastIso = '-' }
}

# Collect referenced .bc + .nc from both .ext files
$ext_files = @('Stagnone_dxy01_15m_new.ext', 'Stagnone_dxy01_15m_old.ext') | ForEach-Object {
    Join-Path $ModelDir $_
} | Where-Object { Test-Path $_ }

$refs = New-Object 'System.Collections.Generic.HashSet[string]'
foreach ($ef in $ext_files) {
    $efLines = Get-Content $ef
    foreach ($ln in $efLines) {
        if ($ln -match '^\s*(forcingFile|discharge|tracer|FILENAME)\s*=\s*(\S+)') {
            [void]$refs.Add($matches[2])
        }
    }
}

# Header
'{0,-12} | {1,-50} | {2,-19} | {3,-19}' -f 'STATUS', 'FILE', 'first time', 'last time' | Write-Host
'{0}-+-{1}-+-{2}-+-{3}' -f ('-' * 12), ('-' * 50), ('-' * 19), ('-' * 19) | Write-Host

$fails = 0
foreach ($f in ($refs | Sort-Object)) {
    $full = Join-Path $ModelDir $f
    if ($f -match '\.bc$')        { $r = Check-Bc $full }
    elseif ($f -match '\.nc$')    { $r = Check-Nc $full }
    else                          { $r = @{ Status = 'SKIP'; FirstIso = '-'; LastIso = '-' } }

    '{0,-12} | {1,-50} | {2,-19} | {3,-19}' -f $r.Status, $f, $r.FirstIso, $r.LastIso | Write-Host
    if ($r.Status -in @('MISSING', 'EARLY_END', 'LATE_START')) { $fails++ }
}

Write-Host ''
if ($fails -eq 0) {
    Write-Host 'ALL OK'
    exit 0
} else {
    Write-Host "FAIL: $fails file(s) don't cover the MDU window."
    Write-Host 'Aborting launch — fix the forcing coverage before re-running.'
    exit 4
}
