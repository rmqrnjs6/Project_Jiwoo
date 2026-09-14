# Judgment & Reevaluation

## 기능

선택된 근거를 바탕으로 현재 판단을 생성하고, 새로운 근거가 추가되었을 때 기존 판단을 다시 확인합니다.

## 폴더 구조

```text
judgment-reevaluation/
├─ README.md
├─ frontend/
│  └─ judgment_reevaluation.js
└─ backend/
   ├─ judgment_engine.py
   └─ tests/
      ├─ test_judgment_engine.py
      └─ test_hardening.py
```

## Frontend

- `judgment_reevaluation.js` : 판단 결과와 재판단 관련 화면 동작

## Backend

- `judgment_engine.py` : AI Judgment 생성 및 판단 상태 처리
- `tests/test_judgment_engine.py` : Judgment Engine 테스트
- `tests/test_hardening.py` : 잘못된 상태 조합과 예외 조건 등에 대한 방어 테스트

## 주요 판단 상태

- `SUPPORTED`
- `CONTRADICTED`
- `UNCERTAIN`
- `INSUFFICIENT_EVIDENCE`

재판단 후 결과가 바뀌면 `JUDGMENT_REVISED`, 그대로면 `JUDGMENT_REAFFIRMED`로 구분합니다.

## 기본 흐름

```text
현재 Evidence
→ Judgment 생성
→ 새로운 Evidence 추가
→ 재판단
→ 유지 또는 변경 기록
```
