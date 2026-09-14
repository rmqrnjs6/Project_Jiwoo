# Case Management

## 기능

사용자가 확인하려는 주제를 Case로 생성하고 조회하는 기능입니다.

Case는 Evidence, Judgment, History 등 이후 데이터가 연결되는 기본 단위입니다.

## 폴더 구조

```text
case-management/
├─ README.md
├─ frontend/
│  └─ case_management.js
└─ backend/
   ├─ main.py
   └─ tests/
      └─ test_api.py
```

## Frontend

- `case_management.js` : Case 생성, 목록 표시, 선택 등 Case 관련 화면 동작

## Backend

- `main.py` : Case 관련 API Endpoint를 포함하는 FastAPI 코드
- `tests/test_api.py` : Case 및 기본 API 동작 테스트

## 기본 흐름

```text
사용자 입력
→ Case 생성
→ 데이터 저장
→ Evidence / Judgment / History의 기준으로 사용
```
