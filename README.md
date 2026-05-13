# whisper-rabbit

[elice](https://elice.io) 의 회의·스크럼을 자동으로 정리하기 위해 만든 사내용 도구. faster-whisper 기반 STT + Claude Code 슬래시 커맨드 `/회의녹음정리` 를 묶어, 음성/영상 파일을 받아 **단일 회의록 docx** 를 자동 생성한다. 표지 다음 첫 페이지는 한 눈에 읽히는 요약(TL;DR · 메타 표 · 핵심 키워드 · 핵심 포인트 · 결정 사항 · 액션 아이템 표 · 미해결 이슈 · 회의 맥락), 그 뒤로 본문 **논의 내용 / 문제점 / 해결방안** 3섹션이 이어진다.

**지원 입력 포맷**: ffmpeg 가 디코드 가능한 모든 컨테이너 — `.mp3` / `.m4a` / `.wav` / `.mp4` / `.mov` / `.opus` / `.flac` 등. 영상 파일은 오디오 트랙만 자동 추출되므로 사전 변환 불필요.

## 주요 기능

- **faster-whisper 1.2+** 기반 STT (CTranslate2 백엔드)
- **BatchedInferencePipeline** 자동 사용 — 일반 transcribe 대비 다회 빠름
- **device/compute_type 자동 선택** — CUDA 있으면 `cuda + float16`, 없으면 `cpu + int8`
- **VAD 필터링** (Silero VAD) + 무음 임계값 조정 가능
- **`condition_on_previous_text=False` 기본** — 긴 회의에서 흔한 hallucination 회피
- **다중 출력 포맷**: `txt` / `srt` / `vtt` / `json`
- **tqdm 진행률 바** — 오디오 길이 대비 처리 위치 표시
- **재현성 메타데이터**: SHA1, 모델, device, compute_type, RTF 등을 JSON에 기록
- **Claude Code 통합**: `/회의녹음정리` 슬래시 커맨드로 받아쓰기 → 회의록 docx 작성까지 자동화

## 요구 사항

- Python 3.10+
- [`ffmpeg`](https://ffmpeg.org/) (PATH 등록)
- (선택) CUDA + cuDNN — GPU 가속 시. 없어도 CPU로 동작.

## 설치

권장 한 줄(설치 + 슬래시 커맨드 동기화 + small 모델 사전 다운로드까지 한 번에):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install.ps1
```

`scripts\install.ps1` 가 다음 세 단계를 순서대로 수행한다.

1. **패키지 editable 설치** — `python -m pip install -e .`
2. **슬래시 커맨드 동기화** — `claude/commands/*.md` → `~/.claude/commands/`
3. **모델 사전 다운로드** — `python -m whisper_rabbit.prefetch small` (1~5분, HuggingFace 캐시 채워둠). **이 단계 덕분에 첫 `/회의녹음정리` 호출이 모델 다운로드로 기다리는 일이 없다.**

옵션:

| 플래그 | 효과 |
|---|---|
| `-SkipPipInstall` | 1단계 건너뛰기 (이미 editable 설치된 경우) |
| `-SkipPrefetch` | 3단계 건너뛰기 (오프라인 환경 또는 직접 모델 선택 원할 때) |
| `-PrefetchModel medium` | 3단계 모델 변경 (`tiny`/`base`/`small`/`medium`/`large-v3` 등) |

editable 설치만 쓰고 싶으면 그냥 `python -m pip install -e .` 도 가능하지만, 첫 호출 시 모델 다운로드(1~5분) 가 발생한다.

## 사용법

### CLI

```powershell
python -m whisper_rabbit "C:\path\to\meeting.m4a" --model small --formats txt,srt,json
```

자주 쓰는 옵션:

| 옵션 | 기본값 | 설명 |
|---|---|---|
| `--model` | `small` | `tiny` / `base` / `small` / `medium` / `large-v3` / `distil-large-v3` |
| `--lang` | `ko` | 언어 코드. 자동 감지하려면 `auto` |
| `--device` | `auto` | `auto` / `cpu` / `cuda` |
| `--compute-type` | `auto` | `auto` / `int8` / `float16` / `bfloat16` 등 |
| `--batch-size` | `8` | BatchedInferencePipeline 배치 크기 |
| `--no-batched` | — | BatchedInferencePipeline 비활성 |
| `--vad-silence-ms` | `500` | VAD 최소 무음 길이(ms). 잘게 끊고 싶으면 낮춘다 |
| `--condition-on-prev` | off | 이전 텍스트 조건화. 짧고 일관된 화자일 때만 권장 |
| `--formats` | `txt,json` | 콤마 구분 출력 포맷 |
| `--out-base` | `<audio>` | 출력 파일 기준 경로 |

출력 파일은 `<out-base>.{txt,srt,vtt,json}` 으로 생성된다. `json`에는 segments + 메타데이터(SHA1, RTF, device 등)가 함께 들어간다.

### Claude Code 슬래시 커맨드

```
/회의녹음정리 "C:\path\to\meeting.m4a"
/회의녹음정리 "C:\path\to\meeting.m4a" --model medium --team 팀2
```

`/회의녹음정리`는 내부적으로 이 CLI를 호출해 transcript 를 만들고, 결과를 읽어 **회의록 docx 한 개**를 Desktop 에 저장한다.

- `<팀명>_회의녹음정리_<날짜>.docx` — 표지 / 회의 요약 / 본문 3섹션이 한 파일에 담긴 정식 회의록
  - 요약 페이지: TL;DR · 메타 표 · 핵심 키워드 · 핵심 포인트 · 결정 사항 · 액션 아이템(docx 네이티브 표 5컬럼) · 미해결 이슈 · 회의 맥락
  - 본문: ■ 1. 논의 내용 / ■ 2. 문제점([주제] 블록) / ■ 3. 해결방안([주제] 블록)

transcript txt/json 은 원본 오디오와 같은 폴더에 남는다 (`<audio>.txt`, `<audio>.json`).

PDF 가 필요하면 워드에서 `파일 → 내보내기 → PDF/XPS 만들기` 로 변환하면 된다 (별도 의존성 없음).

슬래시 커맨드 정의 본체는 [`claude/commands/회의녹음정리.md`](claude/commands/회의녹음정리.md).

## 성능 팁

- **CPU 환경에서 가장 빠른 조합**: `--model small --compute-type int8` + BatchedInferencePipeline 기본 사용 → RTF 0.3~0.6x 수준 (i7/Ryzen 기준).
- **GPU 환경**: `--device cuda --compute-type float16 --model large-v3` 권장. 8GB VRAM 이상이면 large-v3 가능.
- **긴 회의 (1시간+)**: `--condition-on-prev` 켜지 말 것. Whisper 특유의 hallucination 이 길게 이어지는 사례 회피.
- **음질이 나쁘거나 한국어 정확도 우선**: `--model medium`. distil-large-v3 는 영어 위주라 한국어는 large-v3 권장.

## 출력 예시

`transcript.txt`:
```
[00:00:12] 오늘 스크럼 시작하겠습니다.
[00:00:18] 첫 번째 안건은 빌드 환경 차이 이슈입니다.
```

`transcript.json` (요약):
```json
{
  "meta": {
    "audio_sha1": "...",
    "duration_sec": 1834.2,
    "elapsed_sec": 612.4,
    "realtime_factor": 0.334,
    "model_size": "small",
    "device": "cpu",
    "compute_type": "int8",
    "batched": true
  },
  "segments": [
    { "index": 1, "start": 12.0, "end": 16.2, "text": "오늘 스크럼 시작하겠습니다." }
  ]
}
```

## 트러블슈팅

### 첫 실행이 모델 다운로드에서 멈춰 보일 때
`install.ps1` 의 사전 다운로드 단계를 거치면 보통 만나지 않지만, 직접 `pip install -e .` 만 하고 처음 호출했다면 1~5분 동안 진행률 없이 보일 수 있다. 이는 huggingface_hub 가 진행률을 stderr 로 출력하기 때문이며, 백그라운드 실행 시 가려질 수 있다.

5분 이상 진행이 없거나 `HuggingFace xet` 백엔드(LFS 후속)에서 hang 이 의심되면:

1. 현재 프로세스 중단 (Ctrl+C 또는 `Stop-Process`)
2. 캐시 정리:
   ```powershell
   Remove-Item -Recurse -Force "$env:USERPROFILE\.cache\huggingface\hub\models--Systran--faster-whisper-small"
   ```
3. 재시도. 이 도구는 모든 호출 직전에 `HF_HUB_DISABLE_XET=1` 을 자동 set 해 xet 우회 모드로 다운로드한다.

### 모델만 미리 받아두고 싶을 때
```powershell
python -m whisper_rabbit.prefetch small      # 또는 medium / large-v3 등
```

### CUDA 가 잡히지 않을 때
- `python -c "import ctranslate2; print(ctranslate2.get_cuda_device_count())"` 로 ctranslate2 가 CUDA 디바이스를 인식하는지 확인. 0 이면 CUDA-enabled ctranslate2 빌드 또는 cuDNN/CUDA 드라이버 누락. CPU 모드(`--device cpu`)로 우회 가능.

### 산출물이 한글로 깨져 보일 때
콘솔이 cp949 인 경우 출력 텍스트만 깨지고, 실제 파일은 UTF-8 로 정상 저장된다. PowerShell 에서 `Get-ChildItem` 으로 파일명 확인 권장.

## 개발

```powershell
python -m pip install -e .[dev]
pytest
ruff check src tests
```

## 디렉토리 구조

```
whisper-rabbit/
├── src/whisper_rabbit/
│   ├── __init__.py
│   ├── __main__.py        # python -m whisper_rabbit
│   ├── cli.py             # argparse / 진입점
│   ├── device.py          # CUDA 감지·compute_type 결정
│   ├── formats.py         # txt/srt/vtt/json 출력
│   ├── prefetch.py        # 모델 사전 다운로드 진입점
│   └── transcribe.py      # WhisperModel + BatchedInferencePipeline 래핑 + xet 자동 우회
├── claude/commands/
│   └── 회의녹음정리.md       # Claude Code 슬래시 커맨드 정의
├── scripts/
│   └── install.ps1        # 슬래시 커맨드 → ~/.claude/commands/ 동기화
├── tests/
│   ├── test_device.py
│   └── test_formats.py
├── pyproject.toml
├── requirements.txt
└── README.md
```

## 이름의 유래

- **whisper** — faster-**whisper** 모델명 그대로.
- **rabbit** — 사명 **elice** 에 자연스럽게 따라붙는 동물 모티프. 약속 시간에 늦지 않으려 시계를 들고 달리는 토끼처럼, 회의 한 시간 분량 녹음을 RTF 0.3x 안팎으로 따라잡겠다는 도구의 자세에서 따왔다.

사명과 발음을 거꾸로 끼워 맞추려고 만든 이름은 아니고, elice 사내 회의 회고를 자동화하면서 "엘리스 토끼" 라는 별명이 먼저 굳었다.

## 라이선스

[MIT](./LICENSE) — Copyright © 2026 elice.

기여 가이드는 [CONTRIBUTING.md](./CONTRIBUTING.md) 참고.
