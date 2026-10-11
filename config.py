"""
配置模块

集中管理报告生成模块的路径、模板、输出与服务相关配置。
"""

from pathlib import Path

# 项目根目录（本文件所在目录）
BASE_DIR = Path(__file__).resolve().parent

# 模板目录：存放 Jinja2 报告模板
TEMPLATE_DIR = BASE_DIR / "templates"

# 报告模板文件名
REPORT_TEMPLATE_NAME = "report_template.md"

# 示例数据目录
EXAMPLES_DIR = BASE_DIR / "examples"

# 默认输出目录
OUTPUT_DIR = BASE_DIR / "output"

# 默认生成的报告文件名
DEFAULT_OUTPUT_FILENAME = "underwriting_report.md"

# 报告编号前缀
REPORT_NO_PREFIX = "UW"

# 服务信息（供 FastAPI 健康检查接口返回）
SERVICE_NAME = "underwriting report generator"
SERVICE_STATUS = "running"