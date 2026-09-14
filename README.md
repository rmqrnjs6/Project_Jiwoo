# AI Judgment System

**AI Judgment System(지우)**은 여러 주장과 근거를 한곳에서 정리하고,<br> 현재 확인 가능한 자료를 기준으로 판단 결과와 그 변화 과정을 관리하는 프로젝트입니다.

인터넷에서 하나의 이슈를 확인할 때는 여러 출처를 반복해서 찾아보고, 서로 다른 내용을 비교하고, 나중에 새로운 정보가 나오면 다시 확인해야 하는 경우가 많습니다. 이 프로젝트는 그 과정을 하나의 흐름으로 정리하는 것을 목표로 합니다.
---

## 1. 프로젝트 주제

사용자가 확인하려는 주장이나 이슈를 Case로 만들고, 관련 근거를 수집·평가한 뒤 현재 기준의 판단을 생성합니다.

이후 새로운 근거가 추가되면 기존 판단을 다시 확인하고, 판단이 유지되었는지 변경되었는지를 기록합니다.

기본 흐름은 다음과 같습니다.

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
Judgment
= 현재 판단

Permission
= 실행 권한

Action
= 실제 실행
```

---

## 2. 주요 기능

### Case 관리

사용자가 확인하려는 주제를 Case로 생성합니다.

Case는 이후 Evidence, Judgment, History가 연결되는 기준 단위입니다.

### Evidence 탐색 및 선택

관련성이 높은 근거 후보를 확인하고 판단에 사용할 자료를 선택합니다.

근거에는 출처, 핵심 내용, 게시일, 신뢰도, 출처 상태 등을 함께 표시할 수 있습니다.

### 대표 근거

여러 Evidence 중 현재 기준에서 가장 신뢰할 만한 근거를 대표 근거로 사용할 수 있습니다.

대표 근거는 고정된 정답이 아니며, 더 강한 자료가 추가되면 변경될 수 있습니다.

### 신뢰도 평가

Evidence의 품질을 별도로 평가합니다.

평가 항목에는 다음 요소가 사용됩니다.

- 출처의 권위성
- 원본 여부
- 주장과의 직접 관련성
- 최신성
- 다른 근거와의 관계

신뢰도 점수는 사실일 확률을 의미하지 않습니다.

다른 자료와 충돌한다는 이유만으로 해당 Evidence의 품질 점수를 자동으로 낮추지 않습니다.

### 출처 확인

신뢰도와 별도로 출처 자체가 확인 가능한지 점검합니다.

예:

- URL 형식
- 공개 접근 가능 여부
- 원문 존재 여부
- 공식 출처 여부

```text
Source Verification
= 출처를 확인할 수 있는가

Reliability
= 해당 근거의 품질이 어느 정도인가
```

### AI Judgment

선택된 Evidence를 바탕으로 현재 판단을 생성합니다.

주요 결론 상태:

| 상태 | 설명 |
|---|---|
| `SUPPORTED` | 현재 근거가 주장을 지지 |
| `CONTRADICTED` | 현재 근거가 주장과 충돌 |
| `UNCERTAIN` | 현재 자료만으로 판단이 불확실 |
| `INSUFFICIENT_EVIDENCE` | 판단할 근거가 부족 |

판단의 진행 상태는 `RESOLVED`, `UNRESOLVED`, `PENDING` 등으로 별도 관리합니다.

### 재판단

새로운 Evidence나 입력 변경 등이 발생하면 기존 판단을 다시 확인합니다.

```text
판단이 변경됨
→ JUDGMENT_REVISED

다시 확인했지만 판단 유지
→ JUDGMENT_REAFFIRMED
```

기존 판단을 단순히 덮어쓰지 않고 변경 과정이 남도록 구성합니다.

### History / Timeline

시스템 내부의 상세 이벤트는 History에 기록하고, 사용자가 보기 쉬운 주요 변화는 Timeline으로 제공합니다.

예:

```text
근거 부족
→ 새로운 공식 자료 추가
→ 재판단
→ 판단 변경
```

### Decision Snapshot

판단이 만들어진 시점의 주요 조건을 저장합니다.

예:

- 당시 입력
- 사용된 Evidence
- 신뢰도
- 출처 상태
- 모델
- 모델 옵션
- 판단 규칙

이후 자료가 변경되더라도 과거 판단이 어떤 조건에서 생성되었는지 확인할 수 있습니다.

### Permission / Action

AI가 판단할 수 있는 것과 실제로 실행할 수 있는 것을 분리합니다.

Action 실행 전에 최신 판단 여부, Permission, 허용된 Action, 입력값 등을 확인합니다.

### Cost Guard

판단에 영향을 주는 조건이 이전과 동일한 경우 기존 결과를 재사용하여 불필요한 AI 호출을 줄입니다.

### 결과 공유

현재 확인된 핵심, 대표 근거, 아직 확인이 필요한 부분 등을 정리해 다른 사람에게 전달할 수 있도록 구성합니다.

---

## 3. 개발 환경

### Runtime / Framework

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

### Frontend

- HTML
- CSS
- Vanilla JavaScript

### 개발 도구

특정 버전을 프로젝트에서 고정하지 않은 도구는 이름만 표시합니다.

- Visual Studio Code
- Git
- GitHub
- GitHub Desktop
- Docker
- Docker Compose

### OpenAI 기본 설정

현재 소스의 기본값은 다음과 같습니다.

```text
Model: gpt-5.6-luna
Reasoning effort: low
Max output tokens: 1800
Timeout: 30 seconds
```

환경변수로 변경할 수 있습니다.

---

## 4. 기능별 소스 구조

이 저장소는 **업로드와 코드 검토를 쉽게 하기 위해 기능별로 소스코드를 나눈 구조**입니다.

각 기능 폴더에는 별도의 `README.md`가 있으며, 그 안에서 다시 `frontend/`와 `backend/`를 구분합니다.

```text
AI-Judgment-System-upload/
├─ README.md
├─ VERSION.txt
├─ FILE_MANIFEST.txt
│
├─ common/
│  ├─ README.md
│  ├─ frontend/
│  └─ backend/
│
├─ case-management/
│  ├─ README.md
│  ├─ frontend/
│  └─ backend/
│
├─ evidence/
│  ├─ README.md
│  ├─ frontend/
│  └─ backend/
│
├─ reliability-source/
│  ├─ README.md
│  ├─ frontend/
│  └─ backend/
│
├─ judgment-reevaluation/
│  ├─ README.md
│  ├─ frontend/
│  └─ backend/
│
├─ history-timeline/
│  ├─ README.md
│  ├─ frontend/
│  └─ backend/
│
├─ permission-action/
│  ├─ README.md
│  ├─ frontend/
│  └─ backend/
│
├─ sharing-clarity/
│  ├─ README.md
│  ├─ frontend/
│  └─ backend/
│
├─ release-support-response/
│  ├─ README.md
│  ├─ frontend/
│  └─ backend/
│
└─ system-runtime/
   ├─ README.md
   ├─ frontend/
   └─ backend/
```

---

## 5. 기능별 폴더 설명

| 폴더 | 역할 | 상세 설명 |
|---|---|---|
| `common` | 공통 데이터 모델, 스키마, 서비스, 원본 Frontend | [README](common/README.md) |
| `case-management` | Case 생성 및 조회 | [README](case-management/README.md) |
| `evidence` | Evidence 후보 탐색 및 선택 | [README](evidence/README.md) |
| `reliability-source` | 신뢰도 평가 및 출처 확인 | [README](reliability-source/README.md) |
| `judgment-reevaluation` | Judgment 생성 및 재판단 | [README](judgment-reevaluation/README.md) |
| `history-timeline` | 판단 이력과 Timeline | [README](history-timeline/README.md) |
| `permission-action` | 실행 권한 및 Action | [README](permission-action/README.md) |
| `sharing-clarity` | 결과 정리 및 공유 | [README](sharing-clarity/README.md) |
| `release-support-response` | Release Lock, Support, Response 구성 | [README](release-support-response/README.md) |
| `system-runtime` | 실행 환경, DB, OpenAI Runtime, Migration | [README](system-runtime/README.md) |

---

## 6. 주요 소스코드 설명

### `common/`

프로젝트 여러 기능에서 함께 사용하는 코드입니다.

주요 파일:

- `common/backend/models.py`  
  Case, Evidence, Judgment, History 등 데이터 모델

- `common/backend/schemas.py`  
  API 요청/응답 스키마

- `common/backend/services.py`  
  공통 서비스 로직과 Snapshot 관련 처리

- `common/frontend/index.html`  
  원본 브라우저 화면 구조

- `common/frontend/styles.css`  
  전체 UI 스타일

- `common/frontend/app_original.js`  
  기능별로 분류하기 전 RC6 원본 Frontend JavaScript

### `case-management/`

Case 생성과 기본 API 관련 코드를 포함합니다.

### `evidence/`

Evidence 후보 탐색과 관련 테스트를 포함합니다.

### `reliability-source/`

`reliability_engine.py`와 `source_verification.py`를 중심으로 신뢰도와 출처 상태를 처리합니다.

### `judgment-reevaluation/`

`judgment_engine.py`에서 AI Judgment, OpenAI 호출, 오류 처리, 재판단에 필요한 핵심 로직을 관리합니다.

### `history-timeline/`

History 데이터를 사용자에게 보여줄 Timeline 형태로 정리합니다.

### `permission-action/`

Permission을 확인한 뒤 허용된 Action만 실행하도록 처리합니다.

### `sharing-clarity/`

사용자가 현재 결과를 이해하고 공유하는 UI와 관련 테스트를 포함합니다.

### `release-support-response/`

Release Lock, Contextual Support, Response Composer와 관련된 로직을 관리합니다.

### `system-runtime/`

애플리케이션 실행에 필요한 코드가 들어 있습니다.

주요 파일:

- `database.py` : Database 연결 및 세션
- `main.py` : FastAPI 애플리케이션
- `requirements.txt` : Python 의존성
- `scripts/` : Migration 및 OpenAI Smoke Test
- `tests/` : Runtime, Frontend, Health, Release Candidate 테스트

---
