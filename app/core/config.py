import secrets
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "VIGILVOICE Voice Trust Gate"
    API_V1_STR: str = "/api/v1"
    DATABASE_URL: str = "postgresql+asyncpg://vigilvoice@db:5432/vigilvoice"

    MIN_SNR_DB: float = 10.0
    MIN_SPEECH_DURATION_MS: int = 1500
    HIGH_RISK_SPOOF_THRESHOLD: float = 0.75
    ELEVATED_RISK_SPOOF_THRESHOLD: float = 0.40

    VERIFICATION_SECRET: str = Field(default_factory=lambda: secrets.token_urlsafe(32))
    DEMO_VERIFIER_KEY: str = ""
    OTP_TTL_SECONDS: int = 60
    APPROVAL_TTL_SECONDS: int = 60
    MAX_OTP_ATTEMPTS: int = 3
    FILE_EVIDENCE_TTL_SECONDS: int = 120
    STREAM_EVIDENCE_TTL_SECONDS: int = 5
    MAX_AUDIO_BYTES: int = 960044
    SILERO_MODEL_PATH: str = "models/silero_vad.onnx"
    SPOOF_MODEL_PATH: str = "models/spoof_detector.onnx"
    SPOOF_MODEL_VERSION: str = "wav2vec2-xlsr-int8-4b1c4a294ab6"
    THRESHOLD_PROFILE: str = "prototype-uncalibrated-v1"
    EMA_ALPHA: float = 0.3
    VAD_THRESHOLD: float = 0.5
    AUDIO_WINDOW_SECONDS: float = 2.0
    MIN_RMS: float = 0.003
    AUDIO_INFERENCE_TIMEOUT_SECONDS: float = 10.0

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")


settings = Settings()
