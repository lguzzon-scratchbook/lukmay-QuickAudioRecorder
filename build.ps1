$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    if (-not (Get-Command scoop -ErrorAction SilentlyContinue)) {
        Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned -Force
        Invoke-RestMethod -Uri https://get.scoop.sh | Invoke-Expression
        $env:Path = "$env:USERPROFILE\scoop\shims;$env:Path"
    }
    scoop install uv
}

$deps = 'PyQt6', 'soundcard', 'sounddevice', 'soundfile', 'numpy', 'lameenc', 'keyboard', 'pyinstaller'
$withArgs = @()
foreach ($d in $deps) { $withArgs += '--with', $d }
uv run @withArgs pyinstaller --noconsole --onefile --noupx --name QuickAudioRecorder main.py