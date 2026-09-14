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
