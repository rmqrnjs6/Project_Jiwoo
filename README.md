# AI Judgment System

> **완벽을 증명하는 시스템이 아니라, 변화할 수 있음을 증명하는 시스템.**
> **행위 권한 없는 지능은 결국 조언에 머문다.**

AI가 사용자의 입력과 근거(Evidence)를 기반으로 현재의 판단을 형성하고, <br>
새로운 근거가 등장하면 기존 판단을 다시 검토하며 그 변화 과정을 보존하는 실험적 판단 시스템입니다.

현재 프로젝트는 **Private Development** 단계입니다.

---

## 1. Project Overview

일반적인 AI 시스템은 질문을 받고 하나의 답변을 생성하는 데 집중합니다.

이 프로젝트는 그보다 다음 문제에 초점을 맞춥니다.

* AI의 판단은 시간이 지나도 항상 유효한가?
* 더 신뢰할 수 있는 새로운 근거가 등장하면 어떻게 해야 하는가?
* 기존 판단이 틀렸다면 이전 기록을 지워야 하는가?
* AI가 어떤 행동이 필요하다고 판단해도 실행 권한이 없다면?
* 판단할 수 없는 문제는 억지로 결론 내야 하는가?
* 판단이 바뀌지 않았더라도 재검토했다는 사실은 어떻게 기록해야 하는가?

AI Judgment System은 이를 다음 구조로 다룹니다.

```text
INPUT
  ↓
EVIDENCE
  ↓
RELIABILITY ASSESSMENT
  ↓
JUDGMENT
  ↓
PERMISSION
  ↓
ACTION

새로운 Evidence
  ↓
REEVALUATION
  ↓
기존 판단 유지 또는 수정

전체 과정
  ↓
HISTORY
```

---

## 2. Core Philosophy

### Self-Corrective Growth

AI의 성장을 단순히 더 많은 정보를 아는 것으로 정의하지 않습니다.

이 프로젝트에서의 성장은:

> 자신의 판단을 절대화하지 않고, 더 나은 근거가 나타났을 때 기존 판단을 수정할 수 있는 능력

을 의미합니다.

```text
판단
→ 새로운 근거
→ 의심
→ 재검토
→ 유지 또는 수정
```

---

### Judgment Is Not Absolute Truth

Judgment는 절대적인 진리 선언이 아닙니다.

항상 다음 의미를 가집니다.

> **현재 확보된 근거와 현재 평가 규칙을 기준으로 한 판단**

따라서 Judgment는 시간이 지나면서 변경될 수 있습니다.

---

### Intelligence ≠ Permission

AI가 무엇을 해야 하는지 판단할 수 있다고 해서 실제 행동할 권한까지 가지는 것은 아닙니다.

```text
Judgment
= 무엇을 해야 하는가

Permission
= 그것을 할 수 있는가

Action
= 실제로 무엇을 했는가
```

따라서:

> **행위 권한 없는 지능은 결국 조언에 머문다.**

---

### History Preservation

과거의 오류를 단순 삭제하지 않습니다.

가능하면:

```text
기존 판단
↓
새로운 근거
↓
오류 발견
↓
정정
↓
새로운 판단
```

이라는 변화 과정을 보존합니다.

과거가 완벽해서 가치 있는 것이 아니라,

> **왜 그렇게 판단했고, 어디에서 틀렸으며, 어떻게 수정되었는지를 추적할 수 있기 때문에 가치가 있습니다.**

---

## 3. Judgment States

현재 Judgment는 다음 네 가지 결론을 사용합니다.

| State                   | Meaning                     |
| ----------------------- | --------------------------- |
| `SUPPORTED`             | 현재 근거가 입력을 지지               |
| `CONTRADICTED`          | 현재 근거가 입력과 충돌               |
| `UNCERTAIN`             | 신뢰할 만한 근거가 서로 충돌하거나 판단이 불확실 |
| `INSUFFICIENT_EVIDENCE` | 판단에 필요한 근거가 부족              |

AI의 현재 입장은 다음과 같이 연결됩니다.

```text
SUPPORTED
→ AGREE

CONTRADICTED
→ DISAGREE

UNCERTAIN
→ UNSURE

INSUFFICIENT_EVIDENCE
→ UNSURE
```

---

## 4. Resolution State

판단 결과와 별도로 문제의 현재 해결 상태를 관리합니다.

### `RESOLVED`

현재 근거를 기준으로 판단 가능.

### `UNRESOLVED`

현재 확보된 정보로 해결할 수 없음.

예:

```text
신뢰도 높은 근거 A와 B가 서로 충돌
```

### `PENDING`

현재는 판단하기 어렵지만 무엇을 기다리는지가 명확함.

예:

```text
공식 발표 대기
추가 실험 결과 대기
새로운 원본 문서 대기
```

즉:

```text
UNRESOLVED
= 현재로서는 풀리지 않음

PENDING
= 아직은 아님
```

---

## 5. Evidence Reliability

Evidence의 신뢰도는 사용자 입력값 하나만으로 결정하지 않습니다.

현재 `metadata-v2` 평가 방식은 다음 요소를 사용합니다.

```text
Authority
Originality
Directness
Recency
Corroboration
Conflict Penalty
```

예:

```json
{
  "authority": 0.7,
  "originality": 0.6,
  "directness": 0.7,
  "recency": 1.0,
  "corroboration": 0.5,
  "conflict_penalty": 0.0,
  "final_score": 0.68
}
```

### Claimed vs Verified

사용자가:

```text
"이 자료는 공식 1차 자료다."
```

라고 주장했다고 해서 시스템이 즉시 사실로 확정하지 않습니다.

```text
claimed_source_type
≠
verified_source_type
```

Evidence는 기본적으로:

```text
UNVERIFIED
```

상태에서 시작할 수 있습니다.

사용자가 직접 입력한 신뢰도 역시:

```text
USER_PROVIDED
```

로 출처가 명시됩니다.

---

## 6. Reevaluation

새로운 Evidence가 추가되거나 재검토가 요청되면 기존 Judgment를 덮어쓰지 않고 새로운 revision을 생성합니다.

```text
Judgment #1
↓
New Evidence
↓
Reevaluation
↓
Judgment #2
```

판단이 실제로 변경되었다면:

```text
JUDGMENT_REVISED
```

판단이 동일하게 유지되었다면:

```text
JUDGMENT_REAFFIRMED
```

로 기록합니다.

따라서:

> **재판단했다는 사실과 판단이 바뀌었다는 사실은 서로 다릅니다.**

---

## 7. Permission & Action

Action은 Judgment만으로 실행되지 않습니다.

현재 실행 전 다음 조건을 검사합니다.

```text
Latest Judgment?
        ↓
RESOLVED?
        ↓
Execution Permission?
        ↓
Allowed Scope?
        ↓
Valid Parameters?
        ↓
ACTION_COMPLETED
```

하나라도 실패하면:

```text
ACTION_BLOCKED
```

로 기록되며 실제 상태는 변경되지 않습니다.

또한 오래된 Judgment를 근거로 한 Action도 차단합니다.

```text
STALE_JUDGMENT
```

---

## 8. History

시스템 내부의 의미 있는 사건을 History로 보존합니다.

예:

```text
INPUT_CREATED
EVIDENCE_ADDED
DUPLICATE_EVIDENCE_DETECTED

RELIABILITY_ASSESSED
RELIABILITY_REVISED
RELIABILITY_REAFFIRMED

JUDGMENT_CREATED
REEVALUATION_STARTED
JUDGMENT_REVISED
JUDGMENT_REAFFIRMED
REEVALUATION_COMPLETED

PERMISSION_CHANGED

ACTION_ATTEMPTED
ACTION_BLOCKED
ACTION_COMPLETED
ACTION_FAILED
```

History는 단순 로그가 아니라:

> **입력 → 근거 → 판단 → 행동 → 재판단의 변화 경로**

를 추적하기 위한 핵심 계층입니다.

---

## 9. Contextual Support Experiment

향후 버전을 위한 실험적 구조도 일부 포함되어 있습니다.

텍스트에서 관찰 가능한 표현 신호를 기반으로:

```text
NONE
SOFT
EXPLICIT
SAFETY
```

수준의 지원성 응답을 결정할 수 있습니다.

단, 특정 정신질환이나 성격 유형을 텍스트만으로 진단하는 구조는 목표로 하지 않습니다.

```text
관찰 가능한 표현
→ 판단 가능

실제 정신 상태
→ 확정하지 않음

특정 질환 진단
→ 생성하지 않음
```

연기, 창작, 역할극, 인용, 실제 경험 여부가 불명확한 경우에도 이를 고려합니다.

---

## 10. Release Profiles

기능은 단계적으로 공개할 수 있도록 Release Lock 구조를 사용합니다.

```text
V1
- Core Judgment
- Reevaluation

V1.5
+ Permission
+ Action

V2
+ Contextual Nudge
+ Response Composer

V2.5
+ Explain Mode

V3 / INTERNAL
+ Extended capabilities
```

현재 구조는 내부 개발 기능과 실제 공개 범위를 분리하기 위한 기반입니다.

---

## 11. Tech Stack

### Backend

* Python
* FastAPI
* SQLAlchemy
* Pydantic

### Database

Development:

* SQLite

Planned / Production-oriented:

* PostgreSQL

### AI

* OpenAI API integration architecture

실제 모델 호출 품질 검증은 현재 개발 진행 중입니다.

---

## 12. Project Structure

```text
ai-judgment-system/

├─ backend/
│  ├─ app/
│  │  ├─ main.py
│  │  ├─ models.py
│  │  ├─ schemas.py
│  │  ├─ services.py
│  │  └─ ...
│  │
│  ├─ tests/
│  ├─ requirements.txt
│  └─ .env.example
│
├─ docs/
│  ├─ ARCHITECTURE.md
│  ├─ ROADMAP.md
│  └─ ...
│
├─ .github/
│  └─ workflows/
│
├─ README.md
├─ CHANGELOG.md
├─ CONTRIBUTING.md
└─ .gitignore
```

---

## 13. Local Development

### Requirements

Recommended:

```text
Python 3.12.x
```

### Windows PowerShell

```powershell
cd backend

python -m venv .venv

Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1

pip install -r requirements.txt

python -m uvicorn app.main:app --reload
```

가상환경 활성화를 사용하지 않으려면:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

---

## 14. API Documentation

서버 실행 후:

```text
http://127.0.0.1:8000/docs
```

FastAPI Swagger UI에서 API를 직접 테스트할 수 있습니다.

---

## 15. Tests

```bash
cd backend
python -m pytest -q
```

현재 개발 스냅샷 기준:

```text
38 passed
```

이는 현재 작성된 자동 테스트 38개가 통과했다는 의미이며, 전체 시스템의 절대적인 정확성이나 실제 AI 판단 품질을 보장한다는 의미는 아닙니다.

---

## 16. Current Status

현재 단계:

```text
Backend Core     █████████░  ~90%
Architecture     ████████░░  ~80%
User Product     ██████░░░░  ~55-60%
Deployment       ████░░░░░░  ~45%
```

현재 프로젝트는 백엔드 핵심 판단 구조를 구축하고 실제 사용자 경험으로 넘어가기 전 검증 중인 단계입니다.

---

## 17. Known Limitations

현재 명확히 알려진 제한 사항:

* 실제 외부 출처 검증 엔진 미완성
* Semantic Evidence Cross-check 미완성
* 실제 OpenAI API 기반 대규모 판단 품질 검증 미완료
* 사용자 인증 / 접근제어 미완성
* Grace Period 기능 미구현
* Frontend 미구현
* Production migration / monitoring 미완성
* 운영 환경 보안 검증 미완료

이 프로젝트는 이러한 한계를 숨기지 않고 개발 과정에서 지속적으로 수정하는 것을 원칙으로 합니다.

---

## 18. Development Principle

이 프로젝트는 다음 두 문장을 중심 철학으로 사용합니다.

> **완벽을 증명하는 시스템이 아니라, 변화할 수 있음을 증명하는 시스템.**

> **행위 권한 없는 지능은 결국 조언에 머문다.**

목표는 완벽한 AI를 선언하는 것이 아닙니다.

목표는:

```text
판단할 수 있고
↓
틀릴 수 있으며
↓
그 이유를 추적할 수 있고
↓
더 나은 근거를 받아들이며
↓
판단을 수정할 수 있고
↓
권한이 있을 때만 행동할 수 있는
```

시스템을 구축하는 것입니다.

---

## 19. Repository Status

This repository is currently maintained as a **private development repository**.

Public release, licensing, external contribution policy, and production deployment policies have not yet been finalized.
