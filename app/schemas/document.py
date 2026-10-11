from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


SupportedFileType = Literal["pdf", "jpg", "jpeg", "png"]


class Document(BaseModel):
    """一次上传文件的安全元数据，不包含服务器临时路径。"""

    model_config = ConfigDict(extra="forbid")

    document_id: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$",
    )
    original_filename: str = Field(min_length=1)
    file_type: SupportedFileType
    file_size: int = Field(ge=0)
    total_pages: int = Field(ge=0)
