<#
.SYNOPSIS
    Converte um modelo Whisper do HuggingFace para o formato que o VoxFlow carrega.

.DESCRIPTION
    O VoxFlow transcreve com faster-whisper, que só carrega modelos no formato
    CTranslate2. Quase todos os fine-tunes de português são publicados no formato
    Transformers, então precisam de uma conversão — uma vez só, por modelo.

    A conversão precisa de `transformers` e `torch`, que juntos passam de 2 GB. Eles
    NÃO são instalados no ambiente do VoxFlow de propósito: o instalador tem 97 MB e
    manteria isso. Em vez disso, `uv tool run` os empresta só durante a conversão.

    O resultado vai para %LOCALAPPDATA%\VoxFlow\models\<nome>, que é uma das pastas
    que o VoxFlow já varre. Depois é só abrir Ajustes → STT → Procurar de novo.

.PARAMETER Model
    O identificador no HuggingFace, por exemplo 'freds0/distil-whisper-large-v3-ptbr'.

.PARAMETER Name
    Nome da pasta de destino. Por padrão, a última parte do identificador.

.PARAMETER Quantization
    float16 para GPU (padrão), int8 para CPU ou para ocupar menos espaço.

.EXAMPLE
    .\scripts\add-stt-model.ps1 -Model 'nvidia/parakeet-tdt-0.6b-v3'
    Falha de propósito: Parakeet não é Whisper. Veja a lista no README.

.EXAMPLE
    .\scripts\add-stt-model.ps1 -Model 'openai/whisper-large-v3' -Quantization float16
#>
param(
    [Parameter(Mandatory)]
    [string]$Model,
    [string]$Name = '',
    [ValidateSet('float16', 'int8', 'int8_float16', 'float32')]
    [string]$Quantization = 'float16'
)

$ErrorActionPreference = 'Stop'

if (-not $Name) {
    $Name = ($Model -split '/')[-1]
}

$Root = Join-Path $env:LOCALAPPDATA 'VoxFlow\models'
$Target = Join-Path $Root $Name

if (Test-Path -LiteralPath $Target) {
    throw "Já existe um modelo em $Target. Apague-o ou use outro -Name."
}

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw 'uv não encontrado. Ele é necessário para emprestar transformers e torch.'
}

New-Item -ItemType Directory -Path $Root -Force | Out-Null

Write-Output "Convertendo $Model para CTranslate2 ($Quantization)."
Write-Output 'A primeira execução baixa transformers e torch (~2 GB) e o próprio modelo.'
Write-Output "Destino: $Target"

# --copy_files leva o tokenizador e o pré-processador junto: sem eles o faster-whisper
# carrega os pesos e não sabe transformar áudio em features nem números em texto.
uv tool run --from ctranslate2 --with transformers --with torch `
    ct2-transformers-converter `
    --model $Model `
    --output_dir $Target `
    --quantization $Quantization `
    --copy_files tokenizer.json preprocessor_config.json

if ($LASTEXITCODE -ne 0) {
    if (Test-Path -LiteralPath $Target) {
        Remove-Item -LiteralPath $Target -Recurse -Force
    }
    throw @"
A conversão falhou (código $LASTEXITCODE).

O motivo mais comum é o modelo não ser da família Whisper. O conversor só entende
Whisper; Parakeet e Nemotron são NeMo, Qwen3-ASR e Voxtral são LLMs de áudio, e
nenhum deles roda no faster-whisper. Veja a seção "Modelos de transcrição" no README.
"@
}

$ModelBin = Join-Path $Target 'model.bin'
if (-not (Test-Path -LiteralPath $ModelBin)) {
    throw "A conversão terminou sem gerar model.bin em $Target."
}

Write-Output ''
Write-Output "Pronto. $Name está em $Target."
Write-Output 'Abra Ajustes → STT → Procurar de novo e escolha-o em "Modelo instalado".'
