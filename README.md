# whisper-rabbit

[elice](https://elice.io) 의 회의·스크럼을 자동으로 정리하기 위해 만든 사내용 도구. faster-whisper 기반 STT + Claude Code 슬래시 커맨드 `/회의녹음정리` 를 묶어, 음성 파일을 받아 **논의 내용 / 문제점 / 해결방안** 3섹션 회의록 docx로 자동 정리한다.

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

```powershell
# 1) 의존성 + 패키지 editable 설치
python -m pip install -e .

# 2) Claude Code 슬래시 커맨드 동기화 (~/.claude/commands/회의녹음정리.md 로 복사)
powershell -ExecutionPolicy Bypass -File scripts\install.ps1
```

editable 설치를 쓰지 않으면 `python -m pip install -r requirements.txt` 만으로도 모듈 실행은 가능하다.

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

`/회의녹음정리`는 내부적으로 이 CLI를 호출하여 transcript를 만들고, 결과를 읽어 **논의 내용 / 문제점 / 해결방안** 3섹션 docx를 Desktop에 저장한다. 슬래시 커맨드 정의 본체는 [`claude/commands/회의녹음정리.md`](claude/commands/회의녹음정리.md).

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
│   └── transcribe.py      # WhisperModel + BatchedInferencePipeline 래핑
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

미정 (private).
