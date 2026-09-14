# Common

## 기능

여러 기능에서 공통으로 사용하는 코드와 원본 Frontend 파일을 모아둔 폴더입니다.

특정 기능 하나에만 속하지 않는 데이터 모델, API 스키마, 공통 서비스와 화면 기본 파일이 포함되어 있습니다.

## 폴더 구조

```text
common/
├─ README.md
├─ frontend/
│  ├─ index.html
│  ├─ styles.css
│  ├─ common.js
│  └─ app_original.js
└─ backend/
   ├─ __init__.py
   ├─ models.py
   ├─ schemas.py
   └─ services.py
```

## Frontend

- `index.html` : 기본 웹 화면 구조
- `styles.css` : 전체 화면 스타일
- `common.js` : 여러 기능에서 공통으로 사용하는 Frontend 코드
- `app_original.js` : 기능별로 분리하기 전 RC6 원본 `app.js` 보존본

## Backend

- `models.py` : Case, Evidence, Judgment, History 등 공통 데이터 모델
- `schemas.py` : API 요청 및 응답에 사용하는 Pydantic 스키마
- `services.py` : 여러 기능에서 함께 사용하는 서비스 로직
- `__init__.py` : Python 패키지 초기화

## 설명

기능별 폴더에서 공통으로 참조하는 기반 코드입니다.  
업로드용 분류본에서는 중복 파일을 줄이기 위해 공통 요소를 이 폴더에 모았습니다.
