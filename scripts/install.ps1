# whisper-rabbit 슬래시 커맨드 설치 스크립트
#
# 이 저장소의 claude/commands/*.md 를 ~/.claude/commands/ 로 복사한다.
# 이미 같은 이름의 파일이 있으면 덮어쓴다 (백업 .bak 생성).

[CmdletBinding()]
param(
    [switch]$SkipPipInstall
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$srcDir = Join-Path $repoRoot "claude\commands"
$dstDir = Join-Path $env:USERPROFILE ".claude\commands"

if (-not (Test-Path $srcDir)) {
    throw "슬래시 커맨드 원본 디렉토리를 찾을 수 없습니다: $srcDir"
}

New-Item -ItemType Directory -Force $dstDir | Out-Null

# 1) 패키지 editable 설치 (선택)
if (-not $SkipPipInstall) {
    Write-Host "[1/2] python -m pip install -e $repoRoot"
    python -m pip install -e $repoRoot
    if ($LASTEXITCODE -ne 0) { throw "pip install 실패 (exit $LASTEXITCODE)" }
}
else {
    Write-Host "[1/2] pip install 생략 (--SkipPipInstall)"
}

# 2) 슬래시 커맨드 복사
Write-Host "[2/2] 슬래시 커맨드 복사: $srcDir -> $dstDir"
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

Write-Host ""
Write-Host "설치 완료. Claude Code 에서 '/회의녹음정리' 가 보이는지 확인하세요."
