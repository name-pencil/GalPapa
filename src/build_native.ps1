param([Parameter(Mandatory=$true)][string]$OutputDirectory)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$outputRoot = [IO.Path]::GetFullPath($OutputDirectory)
$sourceRoot = Join-Path $projectRoot 'src'
$runtimeRoot = Join-Path $outputRoot 'korean_patch'
New-Item -ItemType Directory -Force -Path $runtimeRoot | Out-Null
$vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
$vs = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
if (-not $vs) { throw 'Visual Studio C++ x86 build tools are required.' }
$dev = Join-Path $vs 'Common7/Tools/VsDevCmd.bat'
Push-Location $runtimeRoot
try {
    $command = '"{0}" -arch=x86 -host_arch=x64 && cl /nologo /utf-8 /std:c++17 /O2 /MT /EHsc /LD "{1}" /link /OUT:galpapa_korean.dll gdi32.lib user32.lib && cl /nologo /utf-8 /std:c++17 /O2 /MT /EHsc "{2}" /link /OUT:GalPapaInject.exe /SUBSYSTEM:WINDOWS user32.lib shell32.lib && cl /nologo /utf-8 /std:c++17 /O2 /MT /EHsc "{3}" /link /OUT:"{4}" /SUBSYSTEM:WINDOWS user32.lib' -f $dev, (Join-Path $sourceRoot 'font_hook.cpp'), (Join-Path $sourceRoot 'injector.cpp'), (Join-Path $sourceRoot 'launcher.cpp'), (Join-Path $outputRoot 'GalPapaLauncher.exe')
    cmd.exe /d /s /c $command
    if ($LASTEXITCODE -ne 0) { throw 'Native build failed' }
} finally { Pop-Location }
