# Reliability & Source Verification

## 기능

근거의 신뢰도 평가와 출처 확인을 담당합니다.

출처가 실제로 확인 가능한지와 근거 자체가 얼마나 신뢰할 만한지는 별개의 정보로 처리합니다.

## 폴더 구조

```text
reliability-source/
├─ README.md
├─ frontend/
│  └─ reliability_source.js
└─ backend/
   ├─ reliability_engine.py
   ├─ source_verification.py
   └─ tests/
      ├─ test_reliability_engine.py
      └─ test_source_verification.py
```

## Frontend

- `reliability_source.js` : 신뢰도 점수와 출처 상태를 화면에 표시

## Backend

- `reliability_engine.py` : Evidence 신뢰도 평가
- `source_verification.py` : URL, 원문, 출처 상태 확인 관련 로직
- `tests/test_reliability_engine.py` : 신뢰도 평가 테스트
- `tests/test_source_verification.py` : 출처 확인 테스트

## 기본 구분

```text
Source Verification
= 출처가 확인 가능한지 점검

Reliability
= 근거 자체의 품질을 평가
```

다른 근거와 내용이 충돌한다는 이유만으로 해당 근거의 신뢰도를 자동으로 낮추지 않습니다.
