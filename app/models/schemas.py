from datetime import datetime
from enum import Enum
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class RiskState(str, Enum):
    LOW = "LOW"
    ELEVATED = "ELEVATED"
    HIGH = "HIGH"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    POOR_QUALITY = "POOR_QUALITY"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"


class StreamEvaluationMessage(BaseModel):
    session_id: str
    risk_state: RiskState
    spoof_score: float | None
    snr_db: float
    speech_duration_ms: int
    reason_codes: list[str]
    model_version: str = "unavailable"
    threshold_profile: str = "prototype-uncalibrated-v1"


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class TransferPayload(StrictRequest):
    # Demo amounts are whole INR; use minor currency units before real integration.
    amount: int = Field(strict=True, gt=0, le=10000000)
    recipient: str = Field(min_length=1, max_length=120)


class ActionRequest(StrictRequest):
    session_id: UUID
    action_type: Literal["fund_transfer"]
    payload: TransferPayload


class ActionResponse(BaseModel):
    action_id: UUID
    session_id: UUID
    action_type: str
    payload: dict
    status: str
    risk_state: RiskState
    allowed: bool = False
    otp_required: bool = True


class OTPVerifyRequest(StrictRequest):
    challenge_id: UUID
    otp_code: str = Field(pattern=r"^[0-9]{6}$")


class CompleteRequest(StrictRequest):
    approval_token: str = Field(min_length=40, max_length=128)


class ChallengeResponse(BaseModel):
    challenge_id: UUID
    expires_at: datetime


class ApprovalResponse(BaseModel):
    approval_token: str
    expires_at: datetime
