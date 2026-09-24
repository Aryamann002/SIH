import secrets
from typing import Literal
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "VIGILVOICE Voice Trust Gate"
    API_V1_STR: str = "/api/v1"
    DATABASE_URL: str = "postgresql+asyncpg://vigilvoice@db:5432/vigilvoice"
    DATABASE_TIMEOUT_SECONDS: float = Field(default=2.0, gt=0, allow_inf_nan=False)

    MIN_SNR_DB: float = Field(default=10.0, allow_inf_nan=False)
    MIN_SPEECH_DURATION_MS: int = Field(default=1500, gt=0)
    HIGH_RISK_SPOOF_THRESHOLD: float = Field(default=0.75, ge=0, le=1, allow_inf_nan=False)
    ELEVATED_RISK_SPOOF_THRESHOLD: float = Field(default=0.40, ge=0, le=1, allow_inf_nan=False)

    VERIFICATION_SECRET: str = Field(default_factory=lambda: secrets.token_urlsafe(32))
    DEMO_VERIFIER_KEY: str = ""
    OTP_TTL_SECONDS: int = Field(default=60, gt=0)
    APPROVAL_TTL_SECONDS: int = Field(default=60, gt=0)
    MAX_OTP_ATTEMPTS: int = Field(default=3, ge=3, le=3)
    FILE_EVIDENCE_TTL_SECONDS: int = Field(default=120, gt=0)
    STREAM_EVIDENCE_TTL_SECONDS: int = Field(default=5, gt=0)
    STREAM_MAX_LAG_SECONDS: float = Field(default=1.5, gt=0, le=5, allow_inf_nan=False)
    STREAM_MAX_AHEAD_SECONDS: float = Field(default=0.4, ge=0, le=1, allow_inf_nan=False)
    MAX_AUDIO_BYTES: int = Field(default=960044, gt=44, le=960044)
    SILERO_MODEL_PATH: str = "models/silero_vad.onnx"
    SPOOF_MODEL_PATH: str = "models/spoof_detector.onnx"
    SPOOF_MODEL_VERSION: str = "wav2vec2-xlsr-int8-4b1c4a294ab6"
    THRESHOLD_PROFILE: str = "prototype-uncalibrated-v1"
    EMA_ALPHA: float = Field(default=0.3, gt=0, le=1, allow_inf_nan=False)
    VAD_THRESHOLD: float = Field(default=0.5, gt=0, le=1, allow_inf_nan=False)
    AUDIO_WINDOW_SECONDS: float = Field(default=2.0, gt=0, le=4, allow_inf_nan=False)
    DETECTOR_INFERENCE_INTERVAL_MS: int = Field(default=600, ge=200, le=2000)
    MIN_RMS: float = Field(default=0.003, ge=0, le=1, allow_inf_nan=False)
    AUDIO_UPLOAD_TIMEOUT_SECONDS: float = Field(default=5.0, gt=0, allow_inf_nan=False)
    AUDIO_CAPACITY_WAIT_SECONDS: float = Field(default=0.1, gt=0, allow_inf_nan=False)
    AUDIO_INFERENCE_QUEUE_TIMEOUT_SECONDS: float = Field(default=1.0, gt=0, allow_inf_nan=False)
    AUDIO_INFERENCE_TIMEOUT_SECONDS: float = Field(default=10.0, gt=0, allow_inf_nan=False)
    JEV_MODE: Literal["disabled", "shadow", "advisory"] = "shadow"
    JEV_API_KEY: str = Field(default="", repr=False)
    JEV_MODEL: str = "jev-1.13.0"
    JEV_TIMEOUT_SECONDS: float = Field(default=0.75, gt=0, le=5, allow_inf_nan=False)
    JEV_ADVISORY_ENABLED: bool = False

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")

    @model_validator(mode="after")
    def validate_policy(self):
        if self.ELEVATED_RISK_SPOOF_THRESHOLD >= self.HIGH_RISK_SPOOF_THRESHOLD:
            raise ValueError("ELEVATED_RISK_SPOOF_THRESHOLD must be below HIGH_RISK_SPOOF_THRESHOLD")
        if self.MIN_SPEECH_DURATION_MS > self.AUDIO_WINDOW_SECONDS * 1000:
            raise ValueError("MIN_SPEECH_DURATION_MS must fit inside AUDIO_WINDOW_SECONDS")
        if self.JEV_MODE == "advisory" and not self.JEV_ADVISORY_ENABLED:
            raise ValueError("Advisory mode requires an explicit shadow-evaluation release gate")
        return self


settings = Settings()
