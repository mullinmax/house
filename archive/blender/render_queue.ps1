# Resumable render queue with a stall watchdog. Usage:
#   powershell -File render_queue.ps1 -Script build_house.py -Config config.toml -Out renders\v2_realism -Jobs exterior,interior -Samples 64
# Frames already on disk are skipped; empty placeholder frames left by a crash are deleted before each (re)start.
param(
    [string]$Script = "build_house.py",
    [string]$Config = "config.toml",
    [string]$Out = "renders",
    [string[]]$Jobs = @("exterior", "interior"),
    [int]$Samples = 64,
    [string]$Res = "",
    [string]$Log = ""
)
$ErrorActionPreference = "Continue"
$Jobs = @($Jobs | ForEach-Object { $_ -split "," } | Where-Object { $_ })   # -File passes "a,b" as one string
Add-Type -Namespace Win -Name Power -MemberDefinition '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint f);'
[Win.Power]::SetThreadExecutionState([uint32]"0x80000001") | Out-Null   # no idle sleep while this runs

$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$blender = "C:\Program Files\Blender Foundation\Blender 5.3\blender.exe"
$ffmpeg = (Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" -Recurse -Filter ffmpeg.exe -ErrorAction SilentlyContinue | Select-Object -First 1).FullName
Set-Location $dir
$outAbs = Join-Path $dir $Out
New-Item -ItemType Directory -Force $outAbs | Out-Null
if (-not $Log) { $Log = Join-Path $outAbs "render_log.txt" }
function L($m) { "$(Get-Date -Format s)  $m" | Out-File -Append -Encoding utf8 $Log }
$expected = @{ exterior = 480; interior = 624 }

foreach ($mode in $Jobs) {
    $t0 = Get-Date
    L "[$mode] start ($Script, $Config, $Samples samples)"
    if ($mode -in "exterior", "interior") {
        $fdir = Join-Path $outAbs $mode
        New-Item -ItemType Directory -Force $fdir | Out-Null
        $tries = 0
        while ($true) {
            Get-ChildItem "$fdir\f_*.png" -ErrorAction SilentlyContinue | Where-Object Length -eq 0 | Remove-Item -Force
            $done = (Get-ChildItem "$fdir\f_*.png" -ErrorAction SilentlyContinue | Where-Object Length -gt 0).Count
            if ($done -ge $expected[$mode] -or $tries -ge 8) { break }
            $tries++
            $a = @("--background", "--python", $Script, "--", "--config", $Config, "--render", $mode, "--out", $Out, "--gpu", "1", "--samples", "$Samples")
            if ($Res) { $a += @("--res", $Res) }
            $p = Start-Process -FilePath $blender -PassThru -NoNewWindow -ArgumentList $a `
                -RedirectStandardOutput "$outAbs\${mode}_blender_$tries.log" -RedirectStandardError "$outAbs\${mode}_blender_$tries.err"
            $last = Get-Date; $lastCount = $done
            while (-not $p.HasExited) {
                Start-Sleep 20
                $c = (Get-ChildItem "$fdir\f_*.png" -ErrorAction SilentlyContinue | Where-Object Length -gt 0).Count
                if ($c -ne $lastCount) { $lastCount = $c; $last = Get-Date }
                elseif (((Get-Date) - $last).TotalMinutes -gt 8) { L "[$mode] stalled at $c frames, restarting"; Stop-Process -Id $p.Id -Force; break }
            }
        }
        $n = (Get-ChildItem "$fdir\f_*.png" | Where-Object Length -gt 0).Count
        L "[$mode] frames done: $n in $([int]((Get-Date) - $t0).TotalMinutes) min, $tries blender runs"
        & $ffmpeg -y -loglevel error -framerate 24 -i "$fdir\f_%04d.png" -c:v libx264 -pix_fmt yuv420p -crf 18 "$outAbs\${mode}_flythrough.mp4"
        L "[$mode] mp4 exit $LASTEXITCODE -> $outAbs\${mode}_flythrough.mp4"
    } else {
        # stills jobs: "stills" (regular set), "dollhouse" (config [dollhouse] set), "dollhouse_stills" (8.6 ft cut set)
        $a = @("--background", "--python", $Script, "--", "--config", $Config, "--gpu", "1", "--samples", "$Samples")
        if ($Res) { $a += @("--res", $Res) }
        if ($mode -eq "stills") { $a += @("--render", "stills", "--out", "$Out\stills") }
        elseif ($mode -eq "dollhouse") { $a += @("--render", "dollhouse", "--out", "$Out\dollhouse_cfg") }
        else { $a += @("--render", "stills", "--out", "$Out\dollhouse", "--only", "dollhouse_southwest,dollhouse_southeast,dollhouse_northeast,dollhouse_northwest,dollhouse_living_closeup,dollhouse_kitchen_closeup,dollhouse_bedrooms_closeup,dollhouse_plan_topdown") }
        $p = Start-Process -FilePath $blender -PassThru -NoNewWindow -Wait -ArgumentList $a `
            -RedirectStandardOutput "$outAbs\${mode}_blender.log" -RedirectStandardError "$outAbs\${mode}_blender.err"
        L "[$mode] done in $([int]((Get-Date) - $t0).TotalMinutes) min (exit $($p.ExitCode))"
    }
}
L "QUEUE DONE"
