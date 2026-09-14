# Permission & Action

## 기능

AI가 내린 판단과 실제 실행 권한을 분리하고, Action 실행 전에 필요한 조건을 확인합니다.

## 폴더 구조

```text
permission-action/
├─ README.md
├─ frontend/
└─ backend/
   ├─ action_engine.py
   └─ tests/
      └─ test_permission_action.py
```

## Frontend

현재 RC6에서 이 기능만을 위한 독립 Frontend 파일은 없습니다.  
관련 화면 동작은 원본 Frontend 구조와 공통 화면에서 처리됩니다.

## Backend

- `action_engine.py` : Permission 확인 및 Action 실행 조건 처리
- `tests/test_permission_action.py` : Permission / Action 동작 테스트

## 실행 전 확인 항목

- 최신 Judgment인지
- 실행 가능한 Judgment 상태인지
- Permission이 존재하는지
- 허용된 Action인지
- Action 파라미터가 유효한지

## 기본 구분

```text
Judgment
= 현재 판단

Permission
= 실행 권한

Action
= 실제 실행
```
