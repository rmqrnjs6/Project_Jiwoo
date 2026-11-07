#!/usr/bin/env python3
"""온행 정책 분기 예비 실험: 독립 재현 가능한 합성 사례.

사용자 계정·예약 ID·개인 기록·외부 서비스에 접근하거나 변경하지 않는다.
이 모델의 통과는 LLM 동작·실제 예약 엔진·현실 문제 해결의 성공을 뜻하지 않는다.
실행: python validation/decision_model.py
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class Scenario:
    name: str
    domain: str = "monitor"  # monitor, assistance, write
    accessible: bool = True
    evidence_verified: bool = True
    significant_change: bool = True
    duplicate: bool = False
    approvals_granted: bool = False
    write_authorized: bool = False
    write_succeeded: bool = False
    readback_matches: bool = False
    harm_risk: str = "low"  # low, high
    recurrence_count: int = 0
    cause_verified: bool = False
    repeated_check_passed: bool = False


def decide(s: Scenario) -> str:
    # 앞선 위험·접근 가능성 판단을 생략하고 성공을 선언하지 않도록 설계.
    if s.harm_risk == "high":
        return "hold_high_risk"
    if not s.accessible or not s.evidence_verified:
        return "hold_unverified"
    if s.recurrence_count >= 2:
        return "reframe_problem"
    if s.domain == "monitor":
        return "quiet" if (not s.significant_change or s.duplicate) else "report_change"
    if s.domain == "assistance":
        if not s.repeated_check_passed:
            return "test_or_recheck"
        return "cause_resolved" if s.cause_verified else "symptom_improved"
    if s.domain == "write":
        if not (s.approvals_granted and s.write_authorized):
            return "draft_only"
        if not s.write_succeeded:
            return "write_failed"
        return "write_verified" if s.readback_matches else "write_unverified"
    return "invalid_domain"


CASES = [
    ("관찰 불가", Scenario("관찰 불가", accessible=False), "hold_unverified"),
    ("검증 전", Scenario("검증 전", evidence_verified=False), "hold_unverified"),
    ("위험 우선", Scenario("위험 우선", harm_risk="high"), "hold_high_risk"),
    ("감시-유의미 변화", Scenario("감시-유의미 변화"), "report_change"),
    ("감시-변화 없음", Scenario("감시-변화 없음", significant_change=False), "quiet"),
    ("감시-기보고", Scenario("감시-기보고", duplicate=True), "quiet"),
    ("동일 실패 반복", Scenario("동일 실패 반복", recurrence_count=2), "reframe_problem"),
    ("지원-재확인 전", Scenario("지원-재확인 전", domain="assistance"), "test_or_recheck"),
    ("지원-증상 개선", Scenario("지원-증상 개선", domain="assistance", repeated_check_passed=True), "symptom_improved"),
    ("지원-원인 해결", Scenario("지원-원인 해결", domain="assistance", repeated_check_passed=True, cause_verified=True), "cause_resolved"),
    ("쓰기-미승인", Scenario("쓰기-미승인", domain="write", write_authorized=True), "draft_only"),
    ("쓰기-권한 없음", Scenario("쓰기-권한 없음", domain="write", approvals_granted=True), "draft_only"),
    ("쓰기-실패", Scenario("쓰기-실패", domain="write", approvals_granted=True, write_authorized=True), "write_failed"),
    ("쓰기-재조회 미확인", Scenario("쓰기-재조회 미확인", domain="write", approvals_granted=True, write_authorized=True, write_succeeded=True), "write_unverified"),
    ("쓰기-검증됨", Scenario("쓰기-검증됨", domain="write", approvals_granted=True, write_authorized=True, write_succeeded=True, readback_matches=True), "write_verified"),
    ("분류 오류", Scenario("분류 오류", domain="unknown"), "invalid_domain"),
]


def main() -> None:
    cases = []
    for i, (name, case, expected) in enumerate(CASES, 1):
        actual = decide(case)
        cases.append({"id": f"R-{i:02d}", "name": name, "expected": expected, "actual": actual, "status": "PASS" if actual == expected else "FAIL"})
    report = {
        "scope": "독립 결정 규칙의 합성 입력 테스트(모의 시험)",
        "out_of_scope": "실제 예약 작업, ChatGPT 모델 준수, 사용자 행동, 사용자 알림 수신",
        "total": len(cases),
        "passed": sum(c["status"] == "PASS" for c in cases),
        "failed": sum(c["status"] == "FAIL" for c in cases),
        "cases": cases,
    }
    output = Path(__file__).with_name("decision_model_results.json")
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"합성 정책 모델: {report['passed']}/{report['total']} PASS")
    raise SystemExit(1 if report["failed"] else 0)


if __name__ == "__main__":
    main()