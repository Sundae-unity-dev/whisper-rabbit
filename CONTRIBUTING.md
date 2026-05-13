# Contributing to whisper-rabbit

기여 환영합니다. 이 도구는 elice 의 회의·스크럼을 자동 정리하기 위해 만들어졌지만, 외부 기여도 환영합니다.

## 개발 환경

- Python 3.10+
- [ffmpeg](https://ffmpeg.org/) (PATH 등록)
- (선택) CUDA + cuDNN — GPU 가속 시

```powershell
git clone https://github.com/Sundae-unity-dev/whisper-rabbit.git
cd whisper-rabbit
python -m pip install -e ".[dev]"
```

## 테스트

```powershell
pytest                                    # 전체 테스트
pytest tests/test_report.py -v            # 특정 모듈
pytest --cov=whisper_rabbit                # 커버리지 포함
```

모든 PR 은 `pytest` 통과 + `ruff check src tests` 통과 필수. GitHub Actions(CI) 가 자동 검증합니다.

## 코드 스타일

- ruff: `E, F, I, UP, B, SIM` 룰 활성 (`pyproject.toml::[tool.ruff.lint]`)
- 한국어 docstring/comments OK
- 새 기능은 단위 테스트 동반
- Windows cp949 콘솔 호환을 위해 CLI 진입점은 `_io_utils.force_utf8_stdio()` 호출

## 커밋 메시지

Conventional Commits 권장:

```
feat(report): ...
fix(transcribe): ...
docs: ...
refactor: ...
test: ...
chore: ...
```

짧은 제목 + 빈 줄 + 본문(왜 그렇게 했는지). 본문은 What 보다 Why 에 집중.

## PR 흐름

1. fork 또는 새 브랜치
2. 변경 + 테스트 + 문서 갱신
3. `pytest` + `ruff check` 통과 확인
4. PR 생성 — [PULL_REQUEST_TEMPLATE](./.github/PULL_REQUEST_TEMPLATE.md) 채워서

## 영역별 가이드

- **report 모듈 변경**: `tests/test_report.py` 에 케이스 추가 + 실제 docx 한 번 열어 페이지·표·목차 확인
- **transcribe 흐름 변경**: 짧은 wav 로 end-to-end smoke 권장
- **슬래시 커맨드 변경**: `scripts/install.ps1 -SkipPipInstall -SkipPrefetch` 로 `~/.claude/commands/` 동기화 후 실제 호출 확인

## 라이선스

기여한 코드는 본 저장소의 [MIT License](./LICENSE) 하에 배포됩니다.
