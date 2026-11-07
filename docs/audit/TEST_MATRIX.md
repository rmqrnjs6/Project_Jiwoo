# 실행 증거와 TC

실행일: 2026-11-08 KST. 환경과 패키지는 [기준선](BASELINE.md) 참조. 모든 파일 보존 실험은 새 임시 디렉터리에서 수행했다.

| TC | 조건 / 입력 | 기대 결과 | 수정 전 실제 | 수정 후 실제 | 근거 |
|---|---|---|---|---|---|
| ASM-001 | notes.txt가 든 기존 출력 폴더 | FileExistsError, 원문 보존 | FAIL: 조립 성공, 기존 폴더 교체 | PASS: 거부, 내용 동일 | tools/tests/test_assemble_runtime.py |
| ASM-002 | 기존 일반 파일 경로 | FileExistsError, 내용 보존 | ERROR: NotADirectoryError | PASS | 동일 |
| ASM-003 | 없는 대상을 가리키는 symlink | 거부, 링크/없는 대상 유지 | FAIL: 대상을 생성함 | PASS | 동일 |
| ASM-004 | 아직 없는 출력 경로 | 실제 실행 Python·화면 원본을 바이트 그대로 복사 | PASS | PASS | 동일 |
| REL-001 | 고정 최신성 0.5, 미검증 official fixture | 최종 0.63, 중립 기여 0.075, 버전/한계 설명 존재 | NOT_RUN: 신규 TC | PASS | test_metadata_policy.py |
| REL-002 | 없음 / 지지 / 반대 peer 목록 | metadata-v3 결과 동일 | NOT_RUN: 신규 TC | PASS | 동일 |
| REG-001 | 기존 조립 백엔드 tests 전체 | 기존 기능 assertion 유지 | 재실행 77 PASS | 79 PASS(기존 77+신규 2) | [전](logs/jiwoo-diagnosis.log), [후](logs/jiwoo-after.log) |
| UI-001 | 실제 app_original.js 구문 | JS 구문 오류 없음 | NOT_RUN | PASS: node --check exit 0 | 런타임 동작/E2E를 뜻하지 않음 |
| OPS-001 | Docker/PostgreSQL 통합 | 컨테이너에서 실행·보존 확인 | NOT_RUN | BLOCKED: docker 없음 | 배포/마이그레이션 미실행 |
| UI-002 | 실제 브라우저 흐름 | 생성·선택·평가·재판단·이력 표시 유지 | NOT_RUN | NOT_RUN | 현재 HTTP 정적 파일 테스트로 대체 성공 선언하지 않음 |

재현 명령(저장소 루트, 준비된 가상환경 사용):

```bash
python -m unittest discover -s tools/tests -v
python tools/assemble_runtime.py --output /tmp/jiwoo-review-new-path
cd /tmp/jiwoo-review-new-path/backend
env -u OPENAI_API_KEY -u DATABASE_URL python -m pytest tests -q
```

`--output`은 매번 없는 경로여야 한다. 출력 경로를 만들기 위해 기존 폴더를 지우지 않는다. 로그의 새 TC와 기존 코드의 버전 연결은 PR diff에서 확인한다. 테스트 실행 후 생성된 SQLite DB는 Git에 포함하지 않는다.
