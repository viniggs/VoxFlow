param(
    [ValidatePattern('^\d+\.\d+\.\d+$')]
    [string]$Version = '0.1.0',
    [ValidateRange(0, 7)]
    [int]$Phase = 0,
    [switch]$SkipValidation
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$ReleaseDir = Join-Path $ProjectRoot "releases\fase-$Phase"
$SourceZip = Join-Path $ReleaseDir "VoxFlow-$Version-fase-$Phase-source.zip"
$TempRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
$StagingDir = Join-Path $TempRoot "VoxFlow-source-$Version-fase-$Phase-$([guid]::NewGuid())"
$InnoCompiler = Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'
if (-not (Test-Path -LiteralPath $InnoCompiler)) {
    $InnoCompiler = Join-Path $env:ProgramFiles 'Inno Setup 6\ISCC.exe'
}
if (-not (Test-Path -LiteralPath $InnoCompiler)) {
    $InnoCompiler = Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 6\ISCC.exe'
}

Set-Location -LiteralPath $ProjectRoot
function Invoke-Checked {
    param(
        [Parameter(Mandatory)]
        [scriptblock]$Command,
        [Parameter(Mandatory)]
        [string]$FailureMessage
    )
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$FailureMessage Código de saída: $LASTEXITCODE"
    }
}

Invoke-Checked { uv sync --extra desktop --extra local-stt --extra dev --extra build } 'Falha ao preparar o ambiente.'
if (-not $SkipValidation) {
    Invoke-Checked { uv run ruff check . } 'Ruff encontrou problemas.'
    Invoke-Checked { uv run pytest } 'Os testes falharam.'
    Invoke-Checked { uv run voxflow --check } 'O diagnóstico de configuração/microfone falhou.'
}
Invoke-Checked { uv run pyinstaller --clean --noconfirm (Join-Path $ProjectRoot 'packaging\voxflow.spec') } 'O PyInstaller falhou.'

New-Item -ItemType Directory -Path $ReleaseDir -Force | Out-Null
New-Item -ItemType Directory -Path $StagingDir -Force | Out-Null

$Excluded = @('.git', '.venv', 'build', 'dist', 'releases', '.pytest_cache', '.ruff_cache', '__pycache__')
Get-ChildItem -LiteralPath $ProjectRoot -Force | Where-Object { $_.Name -notin $Excluded } | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination $StagingDir -Recurse -Force
}
Compress-Archive -Path (Join-Path $StagingDir '*') -DestinationPath $SourceZip -Force
$ResolvedStaging = [System.IO.Path]::GetFullPath($StagingDir)
if (-not $ResolvedStaging.StartsWith($TempRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Diretório temporário fora da raiz esperada: $ResolvedStaging"
}
Remove-Item -LiteralPath $ResolvedStaging -Recurse -Force

if (-not (Test-Path -LiteralPath $InnoCompiler)) {
    throw 'Inno Setup 6 não encontrado. Instale-o antes de gerar o instalador.'
}
Invoke-Checked {
    & $InnoCompiler "/DMyAppVersion=$Version" "/DMyAppPhase=$Phase" "/DBuildRoot=$(Join-Path $ProjectRoot 'dist\VoxFlow')" "/DOutputRoot=$ReleaseDir" (Join-Path $ProjectRoot 'packaging\setup.iss')
} 'O Inno Setup falhou.'

Write-Output "Código: $SourceZip"
Write-Output "Instalador: $(Join-Path $ReleaseDir "VoxFlow-$Version-fase-$Phase-setup.exe")"
