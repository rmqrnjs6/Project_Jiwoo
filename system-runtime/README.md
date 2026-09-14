# System Runtime

## 기능

애플리케이션 실행, 데이터베이스 연결, OpenAI Runtime, Migration, 상태 확인 등 시스템 실행에 필요한 코드를 관리합니다.

## 폴더 구조

```text
system-runtime/
├─ README.md
├─ frontend/
└─ backend/
   ├─ database.py
   ├─ main.py
   ├─ requirements.txt
   ├─ scripts/
   │  ├─ live_openai_smoke_test.py
   │  ├─ migrate_step10_to_step11_sqlite.py
   │  └─ migrate_step11_to_step12_sqlite.py
   └─ tests/
      ├─ test_frontend.py
      ├─ test_openai_runtime.py
      ├─ test_release_candidate.py
      └─ test_system_health.py
```

## Frontend

별도 기능 Frontend는 없으며 애플리케이션 전체 Frontend는 `common/frontend/`에 보존되어 있습니다.

## Backend

- `database.py` : Database 연결 및 세션 관리
- `main.py` : FastAPI 애플리케이션 진입점
- `requirements.txt` : Python 패키지 버전
- `scripts/live_openai_smoke_test.py` : 실제 OpenAI 연결을 확인하기 위한 선택적 Smoke Test
- `scripts/migrate_*.py` : SQLite 데이터 구조 Migration 도구

## Tests

- `test_frontend.py` : Frontend 제공 상태 테스트
- `test_openai_runtime.py` : OpenAI Runtime 및 오류 처리 테스트
- `test_release_candidate.py` : RC 배포 조건 테스트
- `test_system_health.py` : Health / Readiness 관련 테스트

## 주의

유료 OpenAI API 호출이 필요한 Smoke Test는 기본적으로 실행하지 않는 구조입니다.
