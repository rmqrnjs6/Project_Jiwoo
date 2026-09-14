# Evidence

## 기능

판단에 사용할 근거 후보를 탐색하고, 사용자가 확인하고 선택할 수 있도록 제공하는 기능입니다.

## 폴더 구조

```text
evidence/
├─ README.md
├─ frontend/
│  └─ evidence.js
└─ backend/
   ├─ evidence_discovery.py
   └─ tests/
      └─ test_evidence_workspace.py
```

## Frontend

- `evidence.js` : 근거 후보 표시, 선택, 채택 등 Evidence 관련 화면 동작

## Backend

- `evidence_discovery.py` : 관련 Evidence 후보 생성 및 탐색 로직
- `tests/test_evidence_workspace.py` : Evidence 추천 및 작업공간 기능 테스트

## 기본 흐름

```text
Case
→ 관련 근거 후보 탐색
→ 근거 목록 표시
→ 출처와 핵심 내용 확인
→ 사용할 근거 선택
```
