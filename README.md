# 核保评估报告生成模块（underwriting_report_generator）

## 1. 项目介绍

本模块是【分布式光伏财产险 AI 智能核保系统】的独立子项目，负责接收前置 AI 模块输出的结构化分析结果（JSON），自动生成标准化的《分布式光伏财产险AI智能核保评估报告》。

核心链路：

```text
JSON 输入 -> 数据解析(Pydantic) -> 报告生成(Jinja2) -> Markdown 输出 ->（可选）PDF 导出
```

主要能力：

- 严格校验必填字段、风险等级及未知字段，防止不完整数据被误判为低风险；
- 按“拒保 > 加费/附加条件承保 > 正常承保”的优先级形成核保结论；
- 自动生成 Markdown 报告，并支持带中文字体、分页页码的 PDF；
- 对表格中的竖线、换行等输入做安全处理，避免报告排版错位；
- 提供 FastAPI 接口、OpenAPI 文档、三个示例案例和自动化回归测试。

## 2. 系统定位

本模块位于智能核保流程的末端，不直接参与 OCR 识别、图片风险识别、气象分析、组件抗灾能力分析或核保规则判断。它只消费上游模块产出的结构化结果，并按统一格式汇总输出，供核保人员阅读与归档。

## 3. 输入格式

输入为一份结构化 JSON（见 `examples/demo_input.json`），顶层结构：

```json
{
  "project_info": {
    "project_name": "", "insured": "", "location": "", "installation_type": ""
  },
  "material_results": [
    { "material": "", "result": "", "risk_level": "", "description": "", "location": "" }
  ],
  "risk_items": [
    { "risk_type": "", "level": "", "description": "", "source": "", "location": "" }
  ],
  "equipment_analysis": {
    "component_model": "", "hail_rating": "", "wind_rating": "", "snow_rating": "", "risk_level": ""
  },
  "rule_results": [
    { "rule": "", "result": "", "suggestion": "" }
  ]
}
```

校验规则：

- `project_info` 与 `equipment_analysis` 必须提供；
- 项目信息、设备评级和各明细的核心文本字段不能为空；
- 风险等级只接受 `高`、`中`、`低`，同时兼容 `高风险`、`中风险`、`低风险` 写法并自动归一化；
- 未声明的字段会被拒绝，以便尽早发现上游字段名拼写错误；
- 输入不符合结构时，FastAPI 返回标准的 HTTP `422` 校验响应。

## 4. 输出格式

- Markdown 报告（主输出），包含：报告编号、生成时间、风险等级总评、项目基本信息、材料审核结果、风险清单、自然灾害风险、核保规则结果、综合核保意见、风险建议，以及报告结尾免责声明。
- PDF 报告（可选，见 `report_export.py`）。

综合核保决策（decision）三档：

| 情况 | 判断条件 | decision |
| --- | --- | --- |
| 1 | 核保规则结论存在拒保类结论 | 拒保 |
| 2 | 规则结论存在加费、条件承保、附加条件或限制承保 | 加费/附加条件承保 |
| 3 | 存在高风险但无拒保结论 | 加费/附加条件承保 |
| 4 | 以上情况均不存在 | 正常承保 |

## 5. 启动方式

```bash
cd 核保评估
python -m venv .venv
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
# Linux/macOS: source .venv/bin/activate
python -m pip install -r requirements.txt
python main.py          # 默认监听 http://127.0.0.1:8000
```

启动后可访问：

- 健康检查：`http://127.0.0.1:8000/`
- Swagger API 文档：`http://127.0.0.1:8000/docs`
- OpenAPI 描述：`http://127.0.0.1:8000/openapi.json`

生产或局域网部署时，可使用：

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

## 6. API 说明

### GET /

健康检查。

```json
{ "service": "underwriting report generator", "status": "running" }
```

### POST /api/report/generate

接收核保分析结果 JSON，返回决策、风险等级与报告。

```bash
curl -X POST http://127.0.0.1:8000/api/report/generate \
  -H "Content-Type: application/json" \
  --data-binary "@examples/case_A.json"
```

响应：

```json
{
  "status": "success",
  "decision": "正常承保",
  "risk_level": "低",
  "report_no": "UW-20261011-135501-A1B2C3",
  "generated_at": "2026-10-11 13:55:01",
  "report_markdown": "# 分布式光伏财产险AI智能核保评估报告\n..."
}
```

## 7. Demo 运行方法

无需启动服务，直接运行：

```bash
python run_demo.py
```

脚本会依次读取以下三个案例并生成 Markdown / PDF 报告：

| 案例 | 文件 | 场景 | 预期 decision |
| --- | --- | --- | --- |
| A | examples/case_A.json | 屋顶光伏、无涉水、无农业环境、组件风险低 | 正常承保 |
| B | examples/case_B.json | 河流附近、农田、备案含渔光/集中式/林光 | 拒保 |
| C | examples/case_C.json | 轻微遮挡、车棚可燃物、组件抗灾能力不足 | 加费/附加条件承保 |

运行后在项目根目录生成：

```text
report_A.md / report_A.pdf
report_B.md / report_B.pdf
report_C.md / report_C.pdf
```

这些运行时产物已加入 `.gitignore`，不会误提交到代码仓库。

## 8. 运行测试

项目测试只使用 Python 标准库 `unittest`，无需额外安装测试框架：

```bash
python -m unittest discover -s tests -v
```

测试覆盖输入校验、风险等级归一化、决策优先级、API 响应契约、Markdown 表格转义和示例报告生成关键逻辑。

## 9. 目录结构

```text
underwriting_report_generator/
├── main.py                 # FastAPI 服务入口（含报告生成接口）
├── schemas.py              # Pydantic 数据模型
├── generator.py            # 报告生成核心逻辑（Jinja2 渲染）
├── report_export.py        # Markdown -> PDF 导出
├── run_demo.py             # Demo 运行脚本
├── config.py               # 配置项
├── requirements.txt        # 项目依赖
├── README.md               # 项目说明文档
├── .gitignore              # 缓存、虚拟环境与生成报告忽略规则
├── templates/
│   └── report_template.md  # 报告 Markdown 模板
├── examples/
│   ├── demo_input.json     # 通用示例输入
│   ├── case_A.json         # 案例 A：正常承保
│   ├── case_B.json         # 案例 B：拒保
│   └── case_C.json         # 案例 C：加费/附加条件承保
├── tests/
│   ├── test_api.py
│   ├── test_risk_summary.py
│   └── test_schema_and_generator.py
└── utils/
    └── risk_summary.py     # 风险汇总与核保决策逻辑
```
