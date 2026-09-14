"""One-call paid OpenAI smoke test.

This script is intentionally disabled by default so running ordinary tests never
spends API credit. It performs exactly one judgment request when both the API
key and explicit opt-in flag are present.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.judgment_engine import OpenAIJudgmentProvider
from app.models import Case, Evidence, EvidenceSourceType, SourceVerificationStatus


def main() -> int:
    if os.getenv("RUN_PAID_OPENAI_SMOKE_TEST") != "YES":
        print("SKIPPED: set RUN_PAID_OPENAI_SMOKE_TEST=YES to allow one paid OpenAI call.")
        return 0
    if not os.getenv("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY is not configured.")
        return 2

    case = Case(id=1, title="Live smoke test", original_input="프로젝트 코드명은 Atlas다.")
    evidence = Evidence(
        id=1,
        case_id=1,
        content="프로젝트 브리프에는 코드명이 Atlas라고 적혀 있다.",
        claimed_source_type=EvidenceSourceType.PRIMARY,
        claimed_is_primary_source=True,
        source_verification_status=SourceVerificationStatus.UNVERIFIED,
        reliability_score=0.8,
        reliability_source="SYSTEM_TEST",
    )

    provider = OpenAIJudgmentProvider()
    print(f"LIVE TEST: exactly one request will be sent using model={provider.model_name}")
    decision = provider.judge(case=case, evidence=[evidence])
    print("PASS: structured judgment returned")
    print(f"conclusion={decision.conclusion.value}")
    print(f"resolution_state={decision.resolution_state.value}")
    print(f"confidence={decision.confidence}")
    print(f"evidence_assessments={len(decision.evidence_assessments)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
