# History & Timeline

## 기능

시스템에서 발생한 판단과 변경 기록을 보존하고, 사용자가 이해하기 쉬운 Timeline 형태로 정리합니다.

## 폴더 구조

```text
history-timeline/
├─ README.md
├─ frontend/
│  └─ history_timeline.js
└─ backend/
   ├─ timeline.py
   └─ tests/
      └─ test_history_semantics.py
```

## Frontend

- `history_timeline.js` : 판단 변화와 주요 이벤트를 Timeline으로 표시

## Backend

- `timeline.py` : History 데이터를 사용자용 Timeline 데이터로 변환
- `tests/test_history_semantics.py` : REVISED / REAFFIRMED 등 History 의미 검증

## 설명

History는 상세 이벤트 기록에 가깝고, Timeline은 주요 변화를 사람이 읽기 쉬운 형태로 보여주는 기능입니다.

## 기록 보존과 표시 압축

Timeline은 사람이 보기 쉽게 이벤트를 묶거나 요약할 수 있으나, 이는 History 원본의 삭제·수정과 구별합니다. 수정 시점·사유·전후 비교 및 데이터 보존 검증 항목은 [공통 기록 수정·재검증 원칙](../RECORD_REVISION_POLICY.md)에 따릅니다.
