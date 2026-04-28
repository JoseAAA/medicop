from functools import cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración centralizada leída desde variables de entorno / .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = "development"

    database_url: str = "postgresql+asyncpg://medicop:medicop@postgres:5432/medicop"

    redis_url: str = "redis://redis:6379"

    qdrant_host: str = "qdrant"
    qdrant_port: int = 6333
    qdrant_collection_guidelines: str = "clinical_guidelines"

    # Modelo de embeddings (RAG). MiniLM multilingüe = 384 dims, ~120 MB,
    # rápido en CPU. Para mayor calidad se puede usar BAAI/bge-m3 (1024 dims,
    # ~2.3 GB) cuando hay GPU disponible.
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    embedding_dim: int = 384

    ollama_base_url: str = "http://ollama:11434"
    # medgemma1.5:4b — Google Health AI (Gemma 3 base, ~3.3 GB Q4_K_M).
    # Mejor razonamiento clínico de texto + EHR vs medgemma:4b.
    # RTX 3060 6 GB VRAM: cabe completo → ~90 tok/s vs ~20 tok/s en CPU.
    ollama_model: str = "medgemma1.5:4b"
    ollama_timeout: int = 120

    secret_key: str = "dev_secret_key_change_in_production"
    encryption_key: str = "dev_encryption_key_32bytes_long!"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 480
    refresh_token_expire_days: int = 7

    # Whisper — modelo por entorno:
    #   base:            demo rápida · 244M params · ~460 MB VRAM · ~15x real-time
    #   small:           balance demo/calidad · 580 MB VRAM
    #   large-v3-turbo:  producción · 809M params · ~1.5 GB VRAM · excelente español
    whisper_model: str = "base"
    whisper_language: str = "es"
    whisper_compute_type: str = "int8"   # int8 funciona en CPU y GPU sin cambios
    whisper_device: str = "cpu"          # cambiar a "cuda" en Sprint 2 con imagen CUDA

    log_level: str = "INFO"
    log_format: str = "json"

    allowed_origins: str = "http://localhost:3000"

    cmp_validation_enabled: bool = False
    cmp_api_url: str = "https://cmp.org.pe/api/validate"

    # Si True (default en desarrollo), al arrancar el backend siembra pacientes
    # de demostración + guías generadas si la BD está vacía.
    seed_on_startup: bool = True

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",")]

    @property
    def is_development(self) -> bool:
        return self.environment == "development"


@cache
def get_settings() -> Settings:
    """Singleton de configuración — una instancia por proceso."""
    return Settings()
