"""
服务入口模块

基于 FastAPI 提供报告生成服务。
- GET  /                    : 健康检查
- POST /api/report/generate : 接收核保分析结果 JSON，生成评估报告
"""

from datetime import datetime

from fastapi import FastAPI

import config
from generator import ReportGenerator, generate_report_no
from schemas import ReportInput, ReportResponse
from utils import risk_summary

# 创建 FastAPI 应用实例
app = FastAPI(
    title="核保评估报告生成模块",
    description="分布式光伏财产险AI智能核保系统——核保评估报告生成模块",
    version="0.3.0",
)

# 模板环境可安全复用，避免每次请求都重新加载配置。
report_generator = ReportGenerator()


@app.get("/")
def root():
    """服务健康检查接口，返回服务名称与运行状态"""
    return {
        "service": config.SERVICE_NAME,
        "status": config.SERVICE_STATUS,
    }


@app.post(
    "/api/report/generate",
    response_model=ReportResponse,
    summary="生成核保评估报告",
)
def generate_report(data: ReportInput) -> ReportResponse:
    """
    接收一份结构化核保分析结果，生成评估报告。

    返回：
        status: 处理状态
        decision: 综合核保决策（拒保 / 加费/附加条件承保 / 正常承保）
        risk_level: 整体风险等级（高/中/低）
        report_markdown: 完整 Markdown 报告
    """
    decision = risk_summary.make_decision(
        data.rule_results, data.risk_items, data.equipment_analysis, data.material_results
    )
    risk_level = risk_summary.overall_risk_level(
        data.risk_items, data.equipment_analysis, data.material_results
    )
    now = datetime.now()
    report_no = generate_report_no(now)
    generated_at = now.strftime("%Y-%m-%d %H:%M:%S")
    report_markdown = report_generator.generate_report(
        data,
        report_no=report_no,
        generated_at=generated_at,
    )

    return ReportResponse(
        decision=decision,
        risk_level=risk_level,
        report_no=report_no,
        generated_at=generated_at,
        report_markdown=report_markdown,
    )


if __name__ == "__main__":
    # 启动本地开发服务
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
