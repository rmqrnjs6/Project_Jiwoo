# AI Judgment System

> **완벽을 증명하는 시스템이 아니라, 변화할 수 있음을 증명하는 시스템.**
>
> **행위 권한 없는 지능은 결국 조언에 머문다.**

AI Judgment System은 사용자의 입력과 근거(Evidence)를 바탕으로 **현재의 판단**을 만들고,  
새로운 근거나 조건이 생기면 기존 판단을 다시 검토하며, **왜 판단이 유지되거나 바뀌었는지 기록하는 시스템**입니다.

현재 버전은 **`1.0.0-rc1` (Release Candidate)** 입니다.

---

## 이 프로젝트가 하려는 것

일반적인 AI 답변은 한 번 생성되고 끝나는 경우가 많습니다.

이 프로젝트는 다음 질문에서 시작했습니다.

- AI의 판단이 나중에도 항상 맞다고 할 수 있는가?
- 더 좋은 근거가 생기면 기존 판단을 바꿀 수 있어야 하지 않는가?
- 확실하지 않으면 억지로 결론을 내리지 않고 기다릴 수 있는가?
- 판단은 가능해도 실제 행동 권한이 없다면 멈춰야 하지 않는가?
- 판단이 바뀌었다면 왜 바뀌었는지 확인할 수 있어야 하지 않는가?
- 아무것도 바뀌지 않았는데 굳이 유료 AI를 다시 호출해야 하는가?

이를 다음 흐름으로 구현했습니다.

```text
사용자 입력
   ↓
Evidence
   ↓
신뢰도 평가
   ↓
AI Judgment
   ↓
Permission
   ↓
Action

새로운 Evidence / 출처 상태 변화 / 규칙 변화
   ↓
Reevaluation
   ↓
판단 유지 또는 수정

전체 과정
   ↓
History + Timeline
```

---

# 빠르게 테스트하기

## Windows

Python 3.12 사용을 권장합니다.

테스터 패키지를 받은 경우 프로젝트 폴더의:

```text
START_WINDOWS.bat
```

을 실행하면 됩니다.

처음 실행할 때는 자동으로:

```text
가상환경 생성
→ 필요한 Python 패키지 설치
→ 로컬 서버 실행
```

순서로 진행됩니다.

서버가 켜지면 브라우저에서:

```text
http://127.0.0.1:8000/
```

을 엽니다.

서버 종료:

```text
Ctrl + C
```

---

## 직접 실행하고 싶다면

```powershell
cd backend

python -m venv .venv

.\.venv\Scripts\python.exe -m pip install -r requirements.txt

.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

브라우저:

```text
http://127.0.0.1:8000/
```

API 문서:

```text
http://127.0.0.1:8000/docs
```

---

# 처음 테스트하는 순서

처음이라면 아래 순서만 보면 됩니다.

```text
1. Case 만들기
2. Evidence 추가
3. 신뢰도 평가
4. 출처 상태 확인
5. AI 판단 (API Key가 있는 경우)
6. 새 Evidence 추가
7. 재판단
8. Timeline 확인
```

### 간단한 예시

Case:

```text
A 회사가 내년에 새로운 제품을 출시할 것이다.
```

첫 Evidence:

```text
A 회사는 아직 해당 제품의 출시를 공식 발표하지 않았다.
```

그다음 새 Evidence:

```text
A 회사가 공식 홈페이지에서 해당 제품 출시를 발표했다.
```

이렇게 넣으면 **새로운 근거가 들어왔을 때 판단과 Timeline이 어떻게 바뀌는지** 시험할 수 있습니다.

더 자세한 초보자용 테스트 방법은:

```text
TEST_FIRST.md
```

를 참고하세요.

---

# OpenAI API 비용에 대해

OpenAI API는 **선택 사항**입니다.

API Key가 없어도 다음 기능은 로컬에서 사용할 수 있습니다.

- Case 생성
- Evidence 추가
- 신뢰도 평가
- 출처 상태 확인
- History
- Timeline
- 중복 Evidence 검사
- 입력 검증

## 비용이 발생하지 않는 경우

```text
API Key를 환경변수에 넣기
서버 실행
브라우저 열기
Case / Evidence 사용
History / Timeline 조회
```

이 자체로는 OpenAI 모델 요청을 보내지 않습니다.

## 비용이 발생할 수 있는 경우

```text
실제 AI Judgment 요청
```

처럼 OpenAI 모델 호출이 발생할 때입니다.

프로젝트에는 불필요한 호출을 줄이기 위한 **Cost Guard**가 있습니다.

```text
입력 동일
Evidence 동일
신뢰도 동일
출처 상태 동일
규칙 동일
모델 동일
        ↓
기존 Judgment 재사용
        ↓
새 AI 요청 생략
```

또한 AI 요청 전에 입력 크기와 Evidence 개수를 제한해 과도한 요청을 막습니다.

---

# 실제 AI Judgment 사용

본인의 OpenAI API Key가 있는 경우에만 설정하세요.

PowerShell:

```powershell
$env:OPENAI_API_KEY="본인의_API_Key"
```

그다음 서버를 다시 실행합니다.

```powershell
cd backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

> API Key를 README, 채팅, GitHub, 테스트 피드백 파일 등에 붙여넣지 마세요.

테스트가 끝난 뒤 현재 PowerShell 세션에서 제거:

```powershell
Remove-Item Env:OPENAI_API_KEY
```

실제 AI 테스트에 대한 별도 안내:

```text
OPTIONAL_AI_TEST.md
```

---

# 핵심 판단 상태

## Conclusion

| 상태 | 의미 |
|---|---|
| `SUPPORTED` | 현재 근거가 입력을 지지 |
| `CONTRADICTED` | 현재 근거가 입력과 충돌 |
| `UNCERTAIN` | 근거가 충돌하거나 판단이 불확실 |
| `INSUFFICIENT_EVIDENCE` | 판단할 근거가 부족 |

## Resolution

### `RESOLVED`

현재 근거로 판단할 수 있음.

### `UNRESOLVED`

현재 자료로는 풀리지 않음.

### `PENDING`

지금은 결론을 내릴 수 없지만 **무엇을 기다리는지 명확함**.

예:

```text
공식 발표 대기
실험 결과 대기
원본 문서 공개 대기
```

즉:

```text
UNRESOLVED = 현재로서는 알기 어렵다
PENDING    = 아직은 알 수 없다
```

---

# 재판단

새로운 Evidence가 들어왔다고 기존 Judgment를 덮어쓰지 않습니다.

```text
Judgment #1
   ↓
새 Evidence
   ↓
Reevaluation
   ↓
Judgment #2
```

재검토 후 실제 판단이 달라졌다면:

```text
JUDGMENT_REVISED
```

판단이 그대로라면:

```text
JUDGMENT_REAFFIRMED
```

로 구분합니다.

> **다시 생각했다는 것과 생각이 바뀌었다는 것은 서로 다른 사건입니다.**

---

# Evidence와 신뢰도

사용자가:

```text
"이건 공식 1차 자료다."
```

라고 말한 것과 실제로 검증된 것은 구분합니다.

```text
claimed_source
≠
verified_source
```

현재 출처 검증 상태:

```text
UNVERIFIED
PARTIALLY_VERIFIED
VERIFIED
DISPUTED
INVALID
```

신뢰도 역시 사용자가 직접 입력한 값과 시스템 평가를 구분합니다.

현재 Reliability 평가에는 다음 요소가 사용됩니다.

```text
Authority
Originality
Directness
Recency
Corroboration
Conflict Penalty
```

신뢰도 점수는 **절대적인 진실 확률이 아닙니다.**  
현재 시스템이 확보한 정보와 평가 규칙을 기준으로 한 값입니다.

---

# 판단과 행동은 다릅니다

AI가 어떤 행동이 적절하다고 판단했다고 해서 바로 실행하지 않습니다.

```text
Judgment
= 무엇이 적절한가?

Permission
= 행동할 권한이 있는가?

Action
= 실제로 무엇을 했는가?
```

실행 전에는 다음을 확인합니다.

```text
최신 Judgment인가?
↓
RESOLVED 상태인가?
↓
실행 권한이 있는가?
↓
허용된 Action인가?
↓
입력값이 유효한가?
↓
실행
```

오래된 Judgment를 기반으로 한 실행도 차단합니다.

---

# History와 Timeline

## History

시스템이 실제로 겪은 사건을 자세히 보존합니다.

예:

```text
INPUT_CREATED
EVIDENCE_ADDED
DUPLICATE_EVIDENCE_DETECTED

RELIABILITY_ASSESSED
RELIABILITY_REVISED
RELIABILITY_REAFFIRMED

SOURCE_VERIFICATION_ASSESSED
SOURCE_VERIFICATION_REVISED
SOURCE_VERIFICATION_REAFFIRMED

JUDGMENT_CREATED
JUDGMENT_REVISED
JUDGMENT_REAFFIRMED
JUDGMENT_FAILED

REEVALUATION_STARTED
REEVALUATION_COMPLETED

ACTION_ATTEMPTED
ACTION_BLOCKED
ACTION_COMPLETED

AI_CALL_SKIPPED
```

## Timeline

사람이 읽기 쉽도록 중요한 변화를 요약합니다.

```text
Raw History
= 정확한 감사 기록

Timeline
= 사람이 이해하기 위한 기록
```

---

# Decision Snapshot

Judgment가 만들어질 때 **그 당시 AI가 무엇을 봤는지**도 보존합니다.

예:

- 원본 입력
- Evidence 내용
- 당시 Reliability
- 출처 검증 상태
- 사용 모델
- 판단 규칙 버전
- 프롬프트 버전

따라서 나중에 데이터가 바뀌더라도:

> “그 당시에는 무엇을 보고 이런 판단을 했는가?”

를 추적할 수 있도록 설계했습니다.

---

# 테스트 상태

현재 Release Candidate에서 확인된 자동 테스트:

```text
67 passed
```

추가로 로컬에서 확인한 항목:

```text
GET /health        → 200
GET /ready         → 200
GET /system/status → 200
GET /              → Browser UI 200
Python compileall  → passed
```

중요:

> `67 passed`는 **작성된 자동 테스트 67개가 통과했다는 뜻**입니다.  
> 시스템이 절대적으로 틀리지 않는다는 뜻은 아닙니다.

---

# 아직 외부 환경에서 추가 검증이 필요한 것

현재 RC에서는 다음을 “완료”라고 숨겨서 표시하지 않습니다.

- 성공적인 실제 유료 OpenAI Judgment의 Release 검증
- Docker가 설치된 환경에서의 실제 Compose 실행
- PostgreSQL 컨테이너 통합 테스트
- 대규모 실제 사용자 테스트
- Semantic Evidence Cross-check 고도화
- 강한 외부 출처 검증
- 사용자 인증 / 소유권
- 고부하 동시성 처리
- Grace Period 자동화
- 운영 모니터링

이 항목들은 실제 사용 이후 개선 대상으로 남겨두었습니다.

---

# 테스터에게 부탁하고 싶은 것

정상적인 사용만 하지 않아도 됩니다.

오히려 다음처럼 시험해보세요.

- 같은 Evidence를 두 번 넣기
- 같은 버튼을 여러 번 누르기
- 서로 반대되는 Evidence 넣기
- 출처를 모르는 상태로 입력하기
- 아무 변화가 없는데 다시 판단하기
- 새로운 Evidence를 넣고 기존 판단이 어떻게 변하는지 보기

이상한 결과가 나오면:

```text
TEST_FEEDBACK.md
```

에 적어주세요.

버그인지 확신하지 못해도 괜찮습니다.

> **사용자가 이상하다고 느낀 순간 자체가 중요한 테스트 데이터입니다.**

---

# 프로젝트 구조

```text
AI-Judgment-System/
├─ backend/
│  ├─ app/
│  ├─ tests/
│  ├─ scripts/
│  └─ requirements.txt
│
├─ frontend/
│  ├─ index.html
│  ├─ app.js
│  └─ styles.css
│
├─ docs/
├─ README.md
├─ TEST_FIRST.md
├─ TEST_FEEDBACK.md
├─ OPTIONAL_AI_TEST.md
├─ DEVELOPMENT_EXPERIENCE.md
├─ SECURITY.md
├─ Dockerfile
└─ compose.yaml
```

---

# 축적된 개발 경험

이 프로젝트에서 실제로 발견한 문제와 수정 과정은:

```text
DEVELOPMENT_EXPERIENCE.md
```

에 따로 정리했습니다.

주요 경험:

- 판단과 진실을 구분해야 한다
- “모른다”와 “아직 모른다”는 다르다
- 재판단과 판단 변경은 다르다
- 사용자 주장과 검증된 사실은 다르다
- 불필요한 AI 호출도 시스템의 낭비다
- 자동 테스트가 통과해도 설계 구멍은 존재할 수 있다
- 실제 사용자는 개발자가 예상한 방식으로만 행동하지 않는다

---

# 현재 상태

```text
Version: 1.0.0-rc1
Stage: Release Candidate
```

1차 개발 범위의 기능 구현은 완료했고,  
현재 단계는 **실제 사람과 실제 외부 환경에서 사용해보며 검증하는 단계**입니다.

---

# Core Philosophy

> **완벽을 증명하는 시스템이 아니라, 변화할 수 있음을 증명하는 시스템.**

> **행위 권한 없는 지능은 결국 조언에 머문다.**

그리고 이 프로젝트에서 말하는 성장은:

> **더 이상 틀리지 않게 되는 것이 아니라, 틀렸음을 더 빨리 발견하고 더 잘 바꿀 수 있게 되는 것.**
