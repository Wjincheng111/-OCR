import json
import os
import re
import tempfile
from pathlib import Path

from pydantic import BaseModel


def save_result(
    result: BaseModel,
    output_root: Path,
    *,
    document_id: str | None = None,
    filename: str = "result.json",
) -> Path:
    """按 document_id 隔离保存调试 JSON，避免用户文件名参与路径拼接。"""

    resolved_document_id = str(document_id or getattr(result, "document").document_id)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", resolved_document_id):
        raise ValueError("document_id 不能用于结果路径")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\.json", filename):
        raise ValueError("结果文件名不安全")

    resolved_root = output_root.resolve()
    document_dir = (resolved_root / resolved_document_id).resolve()
    if document_dir.parent != resolved_root:
        raise ValueError("结果路径超出输出目录")
    document_dir.mkdir(parents=True, exist_ok=True)
    destination = document_dir / filename
    payload = json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=document_dir,
            prefix=".result-",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary.write(payload)
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_path = Path(temporary.name)
        temporary_path.replace(destination)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
    return destination
