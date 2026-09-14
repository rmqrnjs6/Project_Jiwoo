# Release, Support & Response

## 기능

릴리스 단계별 기능 제어, 보조 안내, 최종 응답 구성과 관련된 로직을 관리합니다.

## 폴더 구조

```text
release-support-response/
├─ README.md
├─ frontend/
└─ backend/
   ├─ release.py
   ├─ response_composer.py
   ├─ support_engine.py
   └─ tests/
      ├─ test_release_and_composer.py
      └─ test_support_engine.py
```

## Frontend

현재 RC6에서 이 기능만을 위한 독립 Frontend 파일은 없습니다.

## Backend

- `release.py` : Release Lock 및 기능 공개 범위 관리
- `response_composer.py` : Judgment와 상태에 따른 사용자 응답 구성
- `support_engine.py` : Contextual Support 관련 보조 처리
- `tests/test_release_and_composer.py` : Release / Response Composer 테스트
- `tests/test_support_engine.py` : Support Engine 테스트

## 설명

내부에 기능이 존재하더라도 현재 릴리스에서 공개되지 않은 기능은 실행되거나 사용자에게 노출되지 않도록 제어하는 역할을 포함합니다.
