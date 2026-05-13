# whisper-rabbit 설치 스크립트
#
# 1) 패키지 editable 설치
# 2) Claude Code 슬래시 커맨드 동기화 (~/.claude/commands/)
# 3) Whisper 모델 사전 다운로드 (기본 small) — 첫 사용 시 다운로드 hang/지연 회피
#
# 옵션:
#   -SkipPipInstall    : 1단계 건너뛰기 (이미 설치된 경우)
#   -SkipPrefetch      : 3단계 건너뛰기 (오프라인 환경 등)
#   -PrefetchModel X   : 사전 다운로드할 모델 (tiny/base/small/medium/large-v3/...). 기본 small

[CmdletBinding()]
param(
    [switch]$SkipPipInstall,
    [switch]$SkipPrefetch,
    [ValidateSet("tiny", "base", "small", "medium", "large-v1", "large-v2", "large-v3", "distil-large-v3")]
    [string]$PrefetchModel = "small"
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$srcDir = Join-Path $repoRoot "claude\commands"
$dstDir = Join-Path $env:USERPROFILE ".claude\commands"

if (-not (Test-Path $srcDir)) {
    throw "슬래시 커맨드 원본 디렉토리를 찾을 수 없습니다: $srcDir"
}

New-Item -ItemType Directory -Force $dstDir | Out-Null

# HuggingFace 다운로드 hang 회피 환경변수 (자식 프로세스에 전파)
$env:HF_HUB_DISABLE_XET = "1"
$env:HF_HUB_DISABLE_SYMLINKS_WARNING = "1"

# 1) 패키지 editable 설치
if (-not $SkipPipInstall) {
    Write-Host "[1/3] python -m pip install -e $repoRoot"
    python -m pip install -e $repoRoot
    if ($LASTEXITCODE -ne 0) { throw "pip install 실패 (exit $LASTEXITCODE)" }
}
else {
    Write-Host "[1/3] pip install 생략 (--SkipPipInstall)"
}

# 2) 슬래시 커맨드 복사
Write-Host "[2/3] 슬래시 커맨드 복사: $srcDir -> $dstDir"
$files = Get-ChildItem -Path $srcDir -Filter "*.md" -File
foreach ($f in $files) {
    $dst = Join-Path $dstDir $f.Name
    if (Test-Path $dst) {
        Copy-Item $dst "$dst.bak" -Force
        Write-Host "  - 백업: $dst -> $dst.bak"
    }
    Copy-Item $f.FullName $dst -Force
    Write-Host "  - 복사: $($f.Name)"
}

# 3) Whisper 모델 사전 다운로드 — hang/지연 회피
if (-not $SkipPrefetch) {
    Write-Host "[3/3] Whisper '$PrefetchModel' 모델 사전 다운로드 (네트워크 상태에 따라 1~5분 소요)"
    python -m whisper_rabbit.prefetch $PrefetchModel
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "모델 사전 다운로드 실패 (exit $LASTEXITCODE) — 첫 사용 시 자동 재시도됩니다"
    }
    else {
        Write-Host "  - 사전 다운로드 완료. 이후 /회의녹음정리 호출 시 캐시에서 즉시 로드됩니다."
    }
}
else {
    Write-Host "[3/3] 모델 사전 다운로드 생략 (--SkipPrefetch)"
}

Write-Host ""
Write-Host "설치 완료. Claude Code 에서 '/회의녹음정리' 가 보이는지 확인하세요."
