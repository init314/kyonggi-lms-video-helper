# 공부 쌀먹 · LMS 다운로드 + 전사

경기대학교 LMS 영상 다운로드 도구인 **Kyonggi LMS Video Helper**에 강의 전사와 요약 프롬프트 생성 기능을 통합했습니다. 하나의 GUI에서 과목·주차를 선택하면 다운로드와 전사가 이어집니다.

## 참고 프로젝트 및 출처

이 프로젝트는 **[Sharon77770/study-ssalmeok](https://github.com/Sharon77770/study-ssalmeok)을 참고하고, 해당 프로젝트의 MIT 라이선스 코드를 활용하여 개발했습니다.**

- 전사 파이프라인, 텍스트 정제·분할, ChatGPT용 프롬프트 생성, PySide6 GUI 및 EXE 빌드 구성을 기반으로 확장했습니다.
- 참고 기준 커밋: [`e79a9ff`](https://github.com/Sharon77770/study-ssalmeok/commit/e79a9ff).
- 기존 LMS 다운로더와 통합하면서 다음 영상 다운로드와 현재 영상 전사의 동시 처리, 가상 디스플레이 다운로드, 메인 디스플레이 설정 창, 트레이 실행 및 중지 처리를 추가했습니다.
- 원저작권 표기와 MIT 라이선스 전문은 [licenses/study-ssalmeok-LICENSE.txt](licenses/study-ssalmeok-LICENSE.txt)에 보존했습니다. 자세한 적용 범위는 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)를 참고하세요.

## 사용

1. `dist\StudySsalmeok\StudySsalmeok.exe` 실행.
2. 실행하면 **1번 또는 2번 메인 화면에 설정 창이 바로 열립니다.**
3. **LMS 다운로드 → 전사** 선택 후 과목명·주차·STT 모델 입력.
4. **시작**을 누르면 `1번 다운로드 → (1번 전사 + 2번 다운로드) → (2번 전사 + 3번 다운로드)`처럼 겹쳐서 처리합니다. 전사는 LMS 영상 순서를 유지하고 다음 영상 한 개까지만 미리 내려받습니다.
5. 설정 창을 닫거나 **트레이로 숨기기**를 눌러도 작업은 계속됩니다. 종료는 트레이 메뉴에서 합니다.

기존 downloadvideo에서 Windows 자격 증명 관리자에 저장한 LMS 계정을 그대로 사용합니다. 계정이 없거나 바꾸려면 **LMS 계정 설정**에서 입력하세요. 비밀번호는 소스나 설정 파일에 저장하지 않습니다.

**내 컴퓨터의 영상·오디오 전사**를 선택하면 기존 로컬 파일 전사 기능도 사용할 수 있습니다. MP4, MKV, MOV, AVI, WebM 등의 영상에서 오디오 트랙을 읽습니다.

## 화면과 백그라운드 실행

- 기본 실행은 **메인 화면에 설정 창을 표시**합니다. 과목명·주차·STT 모델 선택과 시작은 이 창에서 합니다. 콘솔 창은 표시하지 않습니다.
- 설정 창은 마우스가 있는 실제 모니터에 열립니다. 마우스가 가상 화면에 있으면 기본 실제 모니터에 엽니다. **트레이로 숨기기**를 누른 후에는 트레이 아이콘을 더블클릭하거나 우클릭 → **열기**로 다시 표시합니다.
- 다운로드 브라우저는 연결된 세 번째 가상 디스플레이에서 시작합니다. Windows 내부 화면 이름이나 좌표를 고정하지 않고 드라이버 정보로 가상 화면을 찾습니다.
- 두 메인 화면 외에 가상 화면 하나가 연결되어 있어야 합니다. 가상 화면이 없으면 다운로드를 시작하지 않습니다.
- 플레이어는 가상 화면의 같은 창에서 열며 소리는 음소거합니다. 영상 하나를 내려받으면 해당 브라우저를 닫습니다. 전사와 다음 영상 다운로드가 동시에 진행될 수 있고, 전사는 한 번에 하나만 실행됩니다.
- 작업 중 가상 디스플레이를 분리하거나 해상도·배치를 변경하지 마세요. 다운로드 단계에서 연결 변경을 감지하면 중단합니다.
- 작업 완료 팝업이나 알림 풍선은 띄우지 않습니다. 진행·오류는 설정 창의 로그 및 `logs/app.log`에 기록됩니다.
- 중지는 다운로드와 전사 양쪽에 전달되며 다운로드 블록 또는 전사 구간 사이에서 적용됩니다. 첫 모델 다운로드·로딩 중에는 잠시 기다릴 수 있습니다.

## 저장 위치

기본 저장 위치는 소스 실행 시 프로젝트 폴더, EXE 실행 시 EXE가 있는 폴더 아래입니다. 설정 창에서 변경할 수 있습니다.

```text
downloads/<과목>/<주차>주차/001_<영상 제목>.mp4
output/<과목>/<주차>주차/001_<영상 제목>/lecture_<시각>/
    transcript.txt
    cleaned.txt
    source.json
    chunks/chunk_001.txt
    prompts/prompt_001.md
output/<과목>/<주차>주차/latest_result.json
```

다운로드 중인 파일은 `.part`로 쓰고 완료된 파일만 전사합니다. 개별 영상 실패는 로그에 남기고 다음 영상으로 넘어갑니다. 재실행하면 같은 영상을 다시 내려받으며 전사 결과는 새 시각 폴더에 저장합니다.

기존 다운로더와 같이 직접 접근 가능한 MP4/WebM/MOV/M4V 영상을 지원합니다. HLS/DASH 전용 스트리밍은 지원하지 않습니다.

## 개발 환경 실행

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e '.[build]'
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\pythonw.exe src\main.py
```

기본 실행은 설정 창을 메인 화면에 표시합니다. 창 없이 트레이에서만 시작하려면 `--background`를 붙입니다. GUI를 표시하지 않고 지정한 과목을 시작할 수도 있습니다.

```powershell
.\.venv\Scripts\pythonw.exe src\main.py --course '과목명' --week 4
```

STT 모델은 `small`, `medium`, `large-v3`, `large-v3-turbo` 또는 CTranslate2 모델 폴더를 입력합니다. 처음 사용하면 모델을 내려받고 이후 캐시를 사용합니다. 기본 추천은 `large-v3-turbo`입니다.

## RX 9070 XT GPU 설정

AMD Radeon RX 9070 XT에서는 기존 Faster-Whisper/CTranslate2 대신 AMD ROCm용 PyTorch와 Hugging Face Transformers 경로를 사용합니다. AMD ROCm이 감지되면 전사 시 자동으로 Radeon GPU와 FP16을 선택하고, 감지되지 않으면 기존 CPU 경로를 사용합니다. AMD GPU 전사는 Hugging Face Whisper 모델 ID 또는 `small`, `medium`, `large-v3`, `large-v3-turbo` 별칭을 지원합니다.

1. Windows 11과 [AMD가 지원하는 그래픽 드라이버](https://rocm.docs.amd.com/projects/radeon-ryzen/en/latest/docs/install/installrad/windows/install-pytorch.html)를 설치합니다. 현재 AMD 안내서는 ROCm 7.2.1에 Python 3.12와 26.2.2 그래픽 드라이버를 요구합니다.
2. 프로젝트 폴더에서 다음 명령을 실행합니다. ROCm용 별도 `.venv-rocm`을 만들고 AMD PyTorch, 프로젝트 패키지, Chromium을 설치한 뒤 GPU 감지를 확인합니다.

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install_amd_rocm.ps1
```

3. AMD GPU가 포함된 실행파일을 만들려면 `.venv-rocm` 환경에서 빌드합니다.

```powershell
.venv-rocm\Scripts\python.exe -m PyInstaller --noconfirm StudySsalmeok.spec
```

GPU 설정을 마친 뒤에는 모델 입력란에 `large-v3-turbo`를 권장합니다. 한국어 강의의 정확도를 우선하면 `large-v3`를 사용하세요. RX 9070 XT 16GB 메모리에서는 FP16 대형 모델을 사용할 여유가 있습니다. 첫 실행에서 모델 파일을 내려받습니다.

## EXE 빌드

```powershell
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm StudySsalmeok.spec
```

`dist\StudySsalmeok\StudySsalmeok.exe`가 생성됩니다. 배포 시 `StudySsalmeok` 폴더 전체가 필요합니다. STT 모델과 Chromium 브라우저는 EXE에 포함하지 않습니다. 현재 Windows 사용자의 Playwright 브라우저 캐시를 사용하므로 다른 컴퓨터에서도 위의 `playwright install chromium` 단계로 같은 버전의 Chromium을 준비해야 합니다.

## 기존 명령행 도구

기존 `download_lms_video.py`, `watch_lms_lecture.py`, `lms_login.py`도 사용할 수 있습니다. 다운로드와 전사를 자동으로 이어서 처리하려면 위의 통합 GUI를 실행하세요.

```powershell
.\.venv\Scripts\python.exe lms_login.py
.\.venv\Scripts\python.exe download_lms_video.py
.\.venv\Scripts\python.exe watch_lms_lecture.py
```

## 확인

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

다운로드·전사의 동시 진행, 전사 순서와 미리 받는 영상 수 제한, 개별 실패 처리, 양쪽 작업의 중지, 불완전한 다운로드 보호, 가상 화면 선택을 검사합니다. 실제 LMS의 로그인·강의 구성 변경은 사이트 사용 시 확인해야 합니다.
