# 打包群测 zip：dist/NikkeScanner_Beta_v4/ -> NikkeScanner_Beta_v4.zip
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host ">> PyInstaller build..."
python -m PyInstaller NikkeScanner_Beta_v4.spec --noconfirm

$OutDir = Join-Path $Root "dist\NikkeScanner_Beta_v4"
if (-not (Test-Path $OutDir)) {
    throw "Build output not found: $OutDir"
}

# 名录写入 exe 同级（热更新/读写）
Copy-Item -Force (Join-Path $Root "nikke_index.json") (Join-Path $OutDir "nikke_index.json")

$ZipPath = Join-Path $Root "NikkeScanner_Beta_v4.zip"
if (Test-Path $ZipPath) { Remove-Item $ZipPath -Force }
Compress-Archive -Path $OutDir -DestinationPath $ZipPath
Write-Host ">> Done: $ZipPath"
