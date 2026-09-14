# AI Judgment System

**AI Judgment System(지우)**은 여러 주장과 근거를 한곳에서 정리하고, 현재 확인 가능한 자료를 기준으로 판단 결과와 그 변화 과정을 관리하는 프로젝트입니다.

인터넷에서 하나의 이슈를 확인할 때 여러 출처를 반복해서 찾아보고, 서로 다른 내용을 비교하고, 새로운 정보가 나오면 다시 확인해야 하는 경우가 있습니다. 이 프로젝트는 이 과정을 하나의 흐름으로 관리할 수 있도록 구성했습니다.

현재 버전은 **1.0.0-rc6**입니다.

---

## 1. 프로젝트 주제

사용자가 확인하려는 주장이나 이슈를 Case로 만들고, 관련 근거를 수집·평가한 뒤 현재 기준의 판단을 생성합니다.

새로운 근거가 추가되면 기존 판단을 다시 확인하고, 판단이 유지되었는지 변경되었는지를 기록합니다.

```text
Case 생성
→ 관련 근거 확인
→ 출처 및 신뢰도 평가
→ 현재 판단 생성
→ 새로운 근거 추가
→ 재판단
→ 판단 유지 / 변경 기록
→ Timeline 및 공유
```

AI의 판단과 실제 실행 권한은 별도로 관리합니다.

```text
Judgment = 현재 판단
Permission = 실행 권한
Action = 실제 실행
```

---

## 2. 주요 기능

### Case 관리
사용자가 확인하려는 주제를 Case로 생성하고 Evidence, Judgment, History가 연결되는 기준으로 사용합니다.

### Evidence 탐색 및 선택
관련 근거 후보를 확인하고 판단에 사용할 Evidence를 선택합니다. 출처, 핵심 내용, 게시일, 신뢰도, 출처 상태 등을 함께 관리합니다.

### 대표 근거
여러 Evidence 중 현재 기준에서 가장 신뢰할 만한 근거를 대표 근거로 사용할 수 있습니다. 더 강한 자료가 추가되면 대표 근거는 변경될 수 있습니다.

### 신뢰도 평가
출처의 권위성, 원본 여부, 직접 관련성, 최신성 등을 기준으로 Evidence의 품질을 평가합니다. 신뢰도 점수는 사실일 확률을 의미하지 않습니다.

### 출처 확인
URL, 공개 접근 가능 여부, 원문 존재 여부, 공식 출처 여부 등을 점검합니다. 출처 확인과 Evidence 신뢰도 평가는 별도로 처리합니다.

### AI Judgment
현재 Evidence를 바탕으로 다음과 같은 판단 상태를 생성합니다.

| 상태 | 설명 |
|---|---|
| `SUPPORTED` | 현재 근거가 주장을 지지 |
| `CONTRADICTED` | 현재 근거가 주장과 충돌 |
| `UNCERTAIN` | 현재 자료만으로 판단이 불확실 |
| `INSUFFICIENT_EVIDENCE` | 판단할 근거가 부족 |

`RESOLVED`, `UNRESOLVED`, `PENDING`은 판단의 진행 상태를 별도로 나타냅니다.

### 재판단
새로운 Evidence나 입력 변경이 발생하면 다시 판단합니다. 판단이 바뀌면 `JUDGMENT_REVISED`, 유지되면 `JUDGMENT_REAFFIRMED`로 구분합니다.

### History / Timeline
내부 이벤트는 History에 기록하고, 주요 변화는 사용자가 보기 쉬운 Timeline 형태로 제공합니다.

### Decision Snapshot
판단 시점의 입력, Evidence, 신뢰도, 출처 상태, 모델, 규칙 등을 보존해 과거 판단의 기준을 확인할 수 있도록 합니다.

### Permission / Action
Judgment와 실제 실행 권한을 분리하고, Action 실행 전에 최신 판단 여부, Permission, Action 종류와 입력값을 확인합니다.

### Cost Guard
판단에 영향을 주는 조건이 이전과 동일한 경우 기존 결과를 재사용하여 불필요한 AI 호출을 줄입니다.

### 결과 공유
현재 확인된 핵심, 대표 근거, 추가 확인이 필요한 부분 등을 정리해 공유할 수 있도록 구성합니다.

---

## 3. 개발 환경

| 항목 | 버전 |
|---|---:|
| Python | **3.12** |
| FastAPI | **0.116.1** |
| Uvicorn | **0.35.0** |
| SQLAlchemy | **2.0.43** |
| Pydantic | **2.11.7** |
| psycopg | **3.2.9** |
| HTTPX | **0.28.1** |
| OpenAI Python SDK | **3.6.0** |
| Pytest | **8.4.1** |
| PostgreSQL | **17-alpine** |
| Frontend | **HTML / CSS / Vanilla JavaScript** |

버전을 프로젝트에서 고정하지 않은 도구:

- Visual Studio Code
- Git / GitHub / GitHub Desktop
- Docker / Docker Compose

OpenAI 기본 설정:

```text
Model: gpt-5.6-luna
Reasoning effort: low
Max output tokens: 1800
Timeout: 30 seconds
Max input chars: 50000
Max Evidence items: 25
```

---

## 4. 소스 구조

소스는 기능별 폴더로 먼저 나누고, 각 기능 안에서 `frontend/`와 `backend/`를 구분합니다. 모든 기능 폴더에는 별도의 `README.md`가 있습니다.

```text
AI-Judgment-System/
├─ README.md
├─ VERSION.txt
├─ FILE_MANIFEST.txt
├─ Dockerfile
├─ compose.yaml
├─ .dockerignore
├─ .gitignore
├─ .env.example
├─ START_DOCKER.bat
├─ STOP_DOCKER.bat
├─ tools/
│  └─ assemble_runtime.py
│
├─ common/
│  ├─ README.md
│  ├─ frontend/
│  └─ backend/
├─ case-management/
│  ├─ README.md
│  ├─ frontend/
│  └─ backend/
├─ evidence/
│  ├─ README.md
│  ├─ frontend/
│  └─ backend/
├─ reliability-source/
│  ├─ README.md
│  ├─ frontend/
│  └─ backend/
├─ judgment-reevaluation/
│  ├─ README.md
│  ├─ frontend/
│  └─ backend/
├─ history-timeline/
│  ├─ README.md
│  ├─ frontend/
│  └─ backend/
├─ permission-action/
│  ├─ README.md
│  ├─ frontend/
│  └─ backend/
├─ sharing-clarity/
│  ├─ README.md
│  ├─ frontend/
│  └─ backend/
├─ release-support-response/
│  ├─ README.md
│  ├─ frontend/
│  └─ backend/
└─ system-runtime/
   ├─ README.md
   ├─ frontend/
   └─ backend/
```

기능별 폴더 구조는 코드 확인과 업로드에 사용하고, `tools/assemble_runtime.py`가 실제 실행에 필요한 기존 `backend/app + frontend` 형태를 자동으로 조립합니다.

---

## 5. 기능별 폴더 설명

| 폴더 | 역할 |
|---|---|
| `common` | 공통 모델, 스키마, 서비스, 원본 Frontend |
| `case-management` | Case 생성 및 조회 |
| `evidence` | Evidence 후보 탐색 및 선택 |
| `reliability-source` | 신뢰도 평가 및 출처 확인 |
| `judgment-reevaluation` | Judgment 생성 및 재판단 |
| `history-timeline` | History 및 Timeline |
| `permission-action` | 실행 권한 및 Action |
| `sharing-clarity` | 결과 정리 및 공유 |
| `release-support-response` | Release Lock, Support, Response 구성 |
| `system-runtime` | Database, FastAPI Runtime, OpenAI Runtime, Migration |

각 폴더의 파일별 설명은 해당 폴더의 `README.md`에서 확인할 수 있습니다.

---

## 6. 소스코드 및 실행 설명

### 공통 코드

`common/backend/`에는 여러 기능이 함께 사용하는 데이터 모델, API 스키마, 서비스 로직이 있습니다.

`common/frontend/`에는 원본 Frontend가 보존되어 있습니다.

- `index.html`: 화면 구조
- `styles.css`: UI 스타일
- `app_original.js`: RC6 원본 Frontend JavaScript

기능별 Frontend JavaScript는 코드 검토용으로 나눈 사본이며 실제 실행 시에는 `app_original.js`가 `app.js`로 조립됩니다.

### Runtime 조립

기능별 구조를 실행 가능한 구조로 변환하려면 다음 명령을 사용합니다.

```powershell
python tools\assemble_runtime.py
```

기본 출력 위치:

```text
.runtime-build/
├─ backend/
│  ├─ app/
│  ├─ tests/
│  ├─ scripts/
│  └─ requirements.txt
└─ frontend/
   ├─ index.html
   ├─ app.js
   └─ styles.css
```

### Docker

루트의 `Dockerfile`과 `compose.yaml`은 위 Runtime 조립을 Docker 이미지 빌드 과정에서 자동으로 수행합니다.

처음 사용할 때 `.env.example`을 `.env`로 복사합니다.

```powershell
Copy-Item .env.example .env
```

필요하면 `.env`에 OpenAI API Key를 입력합니다.

```env
OPENAI_API_KEY=
```

Docker Desktop이 실행된 상태에서:

```powershell
docker compose up -d --build
```

또는 Windows에서 `START_DOCKER.bat`을 실행하면 같은 작업을 수행합니다.

실행 후:

```text
Web:      http://localhost:8000
API Docs: http://localhost:8000/docs
Ready:    http://localhost:8000/ready
```

`compose.yaml`의 `restart: unless-stopped` 설정으로 Docker Engine이 다시 시작되면 컨테이너도 다시 시작할 수 있습니다. Windows 로그인 시 Docker Desktop 자동 시작 옵션을 함께 사용하면 됩니다.

정지:

```powershell
docker compose stop
```

또는 `STOP_DOCKER.bat`을 사용합니다.
