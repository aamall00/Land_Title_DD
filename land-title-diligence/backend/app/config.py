from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Supabase
    supabase_url: str
    supabase_service_key: str          # service_role key (bypasses RLS for backend ops)
    supabase_anon_key: str
    supabase_storage_bucket: str = "land-documents"

    # Anthropic / Claude
    anthropic_api_key: str
    claude_model: str = "claude-sonnet-4-6"

    # Embedding model (runs locally via sentence-transformers)
    embedding_model: str = "intfloat/multilingual-e5-large"
    embedding_dim: int = 768

    # OCR — choose 'tesseract' or 'textract'
    ocr_provider: str = "tesseract"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "ap-south-1"    # Mumbai — closest to Bangalore

    # App
    app_env: str = "development"
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]
    max_upload_mb: int = 50
    chunk_size: int = 800             # characters per chunk
    chunk_overlap: int = 150

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
