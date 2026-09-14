# Sharing & Clarity

## 기능

현재 확인 결과를 사용자가 이해하기 쉬운 형태로 보여주고, 다른 사람에게 공유할 수 있는 요약을 구성합니다.

## 폴더 구조

```text
sharing-clarity/
├─ README.md
├─ frontend/
│  └─ sharing_clarity.js
└─ backend/
   └─ tests/
      ├─ test_clarity_freedom_ux.py
      └─ test_friendly_memory_ux.py
```

## Frontend

- `sharing_clarity.js` : 현재 확인된 핵심, 확인이 필요한 부분, 공유용 요약 등 관련 UI 동작

## Backend

이 기능을 위한 독립 Backend 서비스 파일은 없으며, 기존 API와 Frontend 조합으로 동작합니다.

테스트 파일:

- `test_clarity_freedom_ux.py` : 확인 결과를 명확하게 보여주는 UX 검증
- `test_friendly_memory_ux.py` : 기록 및 사용자 표현 관련 UX 검증

## 공유 정보 예시

- 확인한 주제
- 현재 확인된 핵심
- 현재 가장 신뢰할 만한 근거
- 아직 확인이 필요한 부분
- 원문 출처
- 확인 시점
