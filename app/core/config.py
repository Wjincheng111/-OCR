from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """可通过环境变量或项目根目录下的 .env 覆盖的配置。"""

    app_name: str = "分布式光伏财产险 OCR 与信息提取模块"
    debug: bool = False
    output_dir: Path = Path("output")
    max_file_size_mb: int = Field(default=20, gt=0)
    max_pdf_pages: int = Field(default=50, gt=0)
    max_image_pixels: int = Field(default=40_000_000, gt=0)
    max_pdf_total_pixels: int = Field(default=200_000_000, gt=0)
    max_package_files: int = Field(default=20, ge=2, le=100)
    max_package_size_mb: int = Field(default=100, gt=0)
    max_json_body_mb: int = Field(default=25, gt=0)
    max_concurrent_ocr: int = Field(default=1, ge=1, le=8)
    pdf_dpi: int = Field(default=200, ge=72, le=600)
    ocr_language: str = "ch"
    ocr_device: str = "cpu"
    ocr_enable_mkldnn: bool = False
    ocr_model_cache_dir: Path | None = None
    save_results: bool = False
    classification_review_threshold: float = Field(default=0.55, ge=0.0, le=1.0)
    field_confidence_review_threshold: float = Field(default=0.70, ge=0.0, le=1.0)
    ocr_confidence_review_threshold: float = Field(default=0.75, ge=0.0, le=1.0)

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024

    @property
    def max_package_size_bytes(self) -> int:
        return self.max_package_size_mb * 1024 * 1024

    @property
    def max_json_body_bytes(self) -> int:
        return self.max_json_body_mb * 1024 * 1024

    @property
    def resolved_output_dir(self) -> Path:
        path = self.output_dir
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return path.resolve()

    @property
    def resolved_ocr_model_cache_dir(self) -> Path | None:
        if self.ocr_model_cache_dir is None:
            return None
        path = self.ocr_model_cache_dir
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return path.resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()
