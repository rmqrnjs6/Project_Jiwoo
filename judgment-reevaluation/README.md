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

## 기록 수정 기준

원본 판단과 최신 판단을 구분하고, 새로운 근거·반례에 따른 재평가 사유 및 이전/이후 상태를 추적합니다. 명확한 지지/반대 외에 근거 부족 상태를 유지하며, %를 사실의 확률로 단정하지 않습니다. 구현 검증 사항은 [공통 기록 수정·재검증 원칙](../RECORD_REVISION_POLICY.md)을 따릅니다.
