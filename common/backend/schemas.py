from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

from .models import (
    AIPosition,
    ActionBlockReason,
    ActionStatus,
    ActionType,
    CaseStatus,
    ContextMode,
    DeliveryStyle,
    EvidenceSourceType,
    HistoryEventType,
    JudgmentConclusion,
    JudgmentOrigin,
    NudgeLevel,
    ReevaluationTrigger,
    ResolutionState,
    SourceVerificationStatus,
)


class UTCReadModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    @field_validator("*", mode="before")
    @classmethod
    def normalize_datetimes_to_utc(cls, value):
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value.astimezone(timezone.utc)
        return value


class CaseCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "title": "첫 수동 테스트",
                "original_input": "나는 A라는 정보가 사실이라고 생각한다.",
            }
        }
    )

    title: str = Field(min_length=2, max_length=200)
    original_input: str = Field(min_length=3)

    @field_validator("title", "original_input", mode="before")
    @classmethod
    def strip_case_text(cls, value):
        return value.strip() if isinstance(value, str) else value


class EvidenceCreate(BaseModel):
    content: str = Field(min_length=2)
    source_type: EvidenceSourceType
    source_url: HttpUrl | None = None
    is_primary_source: bool = False
    source_published_at: datetime | None = None
    reliability_score: float | None = Field(default=None, ge=0.0, le=1.0)

    @field_validator("content", mode="before")
    @classmethod
    def strip_evidence_content(cls, value):
        return value.strip() if isinstance(value, str) else value


class EvidenceRead(UTCReadModel):

    id: int
    case_id: int
    content: str
    claimed_source_type: EvidenceSourceType
    claimed_is_primary_source: bool
    source_verification_status: SourceVerificationStatus
    verified_source_type: EvidenceSourceType | None
    verified_is_primary_source: bool | None
    effective_source_type: EvidenceSourceType
    effective_is_primary_source: bool
    source_url: str | None
    reliability_score: float | None
    reliability_source: str
    source_published_at: datetime | None
    created_at: datetime


class EvidenceDiscoveryRequest(BaseModel):
    limit: int = Field(default=6, ge=5, le=10)


class EvidenceCandidateRead(UTCReadModel):
    id: int
    case_id: int
    title: str
    summary: str
    source_name: str
    source_url: str
    source_type: EvidenceSourceType
    source_published_at: datetime | None
    relation_to_claim: str
    reliability_score: float
    score_components: dict
    rationale: str
    source_verification_status: SourceVerificationStatus
    is_representative: bool
    active: bool
    origin: str
    adopted_evidence_id: int | None
    created_at: datetime


class EvidenceCandidateBatchRead(BaseModel):
    candidates: list[EvidenceCandidateRead]
    representative_id: int | None
    origin: str
    disclaimer: str


class SourceVerificationRead(UTCReadModel):

    id: int
    case_id: int
    evidence_id: int
    revision_no: int
    status: SourceVerificationStatus
    verified_source_type: EvidenceSourceType | None
    verified_is_primary_source: bool | None
    rationale: str
    checks: dict
    method_version: str
    actor: str
    created_at: datetime


class ReliabilityAssessmentRead(UTCReadModel):

    id: int
    case_id: int
    evidence_id: int
    revision_no: int
    authority_score: float
    originality_score: float
    directness_score: float
    recency_score: float
    corroboration_score: float
    final_score: float
    rationale: str
    method_version: str
    created_at: datetime


class JudgmentCreate(BaseModel):
    conclusion: JudgmentConclusion
    ai_position: AIPosition
    confidence: float = Field(ge=0.0, le=1.0)
    resolution_state: ResolutionState
    position_text: str = Field(min_length=1)
    reasoning_summary: str = Field(min_length=1)
    unresolved_reason: str | None = None
    waiting_for: str | None = None
    evidence_assessments: list[dict] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_resolution_details(self):
        expected_position = {
            JudgmentConclusion.SUPPORTED: AIPosition.AGREE,
            JudgmentConclusion.CONTRADICTED: AIPosition.DISAGREE,
            JudgmentConclusion.UNCERTAIN: AIPosition.UNSURE,
            JudgmentConclusion.INSUFFICIENT_EVIDENCE: AIPosition.UNSURE,
        }[self.conclusion]
        if self.ai_position != expected_position:
            raise ValueError(
                f"ai_position must be {expected_position.value} for {self.conclusion.value}"
            )

        unresolved_conclusions = {
            JudgmentConclusion.UNCERTAIN,
            JudgmentConclusion.INSUFFICIENT_EVIDENCE,
        }
        resolved_conclusions = {
            JudgmentConclusion.SUPPORTED,
            JudgmentConclusion.CONTRADICTED,
        }

        if self.resolution_state == ResolutionState.PENDING:
            if not self.waiting_for:
                raise ValueError("PENDING judgment requires waiting_for")
            if self.conclusion not in unresolved_conclusions:
                raise ValueError("PENDING requires UNCERTAIN or INSUFFICIENT_EVIDENCE")

        if self.resolution_state == ResolutionState.UNRESOLVED:
            if not self.unresolved_reason:
                raise ValueError("UNRESOLVED judgment requires unresolved_reason")
            if self.conclusion not in unresolved_conclusions:
                raise ValueError("UNRESOLVED requires UNCERTAIN or INSUFFICIENT_EVIDENCE")

        if self.resolution_state == ResolutionState.RESOLVED:
            if self.waiting_for:
                raise ValueError("RESOLVED judgment cannot have waiting_for")
            if self.conclusion not in resolved_conclusions:
                raise ValueError("RESOLVED requires SUPPORTED or CONTRADICTED")
        return self


class JudgmentRead(UTCReadModel):

    id: int
    case_id: int
    previous_judgment_id: int | None
    revision_no: int
    conclusion: JudgmentConclusion
    ai_position: AIPosition
    confidence: float
    resolution_state: ResolutionState
    position_text: str
    reasoning_summary: str
    unresolved_reason: str | None
    waiting_for: str | None
    evidence_assessments: list[dict]
    origin: JudgmentOrigin
    actor: str
    reevaluation_trigger: ReevaluationTrigger | None
    decision_fingerprint: str | None
    created_at: datetime


class SupportAssessmentRead(UTCReadModel):

    id: int
    case_id: int
    source_text: str
    expression_summary: str
    affect_signals: list[dict]
    context_mode: ContextMode
    context_rationale: str
    nudge_level: NudgeLevel
    delivery_style: DeliveryStyle
    recommendation_text: str | None
    rationale_summary: str
    created_at: datetime


class CaseSummaryRead(UTCReadModel):

    id: int
    title: str
    status: CaseStatus
    created_at: datetime
    updated_at: datetime


class CaseRead(UTCReadModel):

    id: int
    title: str
    original_input: str
    status: CaseStatus
    created_at: datetime
    updated_at: datetime
    evidence: list[EvidenceRead] = []
    judgments: list[JudgmentRead] = []
    support_assessments: list[SupportAssessmentRead] = []


class HistoryRead(UTCReadModel):

    id: int
    case_id: int
    event_type: HistoryEventType
    entity_type: str
    entity_id: int | None
    actor: str
    payload: dict
    created_at: datetime


class TimelineItemRead(UTCReadModel):
    event_id: int
    event_type: HistoryEventType
    category: str
    title: str
    summary: str
    entity_type: str
    entity_id: int | None
    occurred_at: datetime
    event_count: int = 1


class ReleaseRead(BaseModel):
    profile: str
    features: dict[str, bool]


class ResponseCompositionRead(BaseModel):
    case_id: int
    judgment_id: int
    support_assessment_id: int | None
    text: str
    judgment_text: str
    nudge_text: str | None
    change_notice: str | None
    delivery_style: DeliveryStyle


class PermissionUpdate(BaseModel):
    can_execute: bool
    allowed_actions: list[ActionType] = Field(default_factory=list)


class PermissionRead(UTCReadModel):

    id: int
    case_id: int
    can_execute: bool
    allowed_actions: list[str]
    updated_at: datetime


class ActionExecuteRequest(BaseModel):
    judgment_id: int = Field(gt=0)
    action_type: ActionType
    parameters: dict = Field(default_factory=dict)


class ActionRead(UTCReadModel):

    id: int
    case_id: int
    judgment_id: int
    action_type: ActionType
    parameters: dict
    status: ActionStatus
    result: dict
    blocked_reason: ActionBlockReason | None
    actor: str
    created_at: datetime
