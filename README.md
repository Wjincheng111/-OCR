# OCR 与信息提取模块

## 1. 项目是什么

这是“分布式光伏财产险 AI 智能核保系统”中的独立材料数字化子项目。它负责把 PDF 或图片转换为带来源证据的结构化 JSON，供后续系统使用。

本项目只处理材料和数据质量，不计算保费，不做风险评分，也不输出承保、拒保等核保结论。

## 2. 当前已经实现什么

当前版本已形成一个可独立运行的完整规则型基线，包含：

- PDF、JPG、JPEG、PNG 上传、文件头校验、大小限制和临时文件自动清理；
- 图片 EXIF 方向修正、RGB 转换和像素上限；
- PDF 页数、单页像素及总渲染像素限制，并逐页处理；
- PaddleOCR 3.x 封装，同时兼容常见的 2.x 返回格式；
- OCR 文字、置信度、四点坐标、页码和文件元数据标准化；
- 13 种文档类型的可解释规则分类及逐页分类；
- 混合材料 PDF 提醒；
- 项目、投保、组件、逆变器、设备清单、合同、检测和验收字段提取；
- 日期、金额、数量及 W/kW/MW 的标准化；
- 简单设备表按行提取，保留每个单元格的 OCR 证据；
- 必填项、置信度、同文档冲突、日期区间和数量×功率等数据校验；
- 同一项目多文档的项目名称、地点、容量、保险期间、保险金额和设备数量一致性校验；
- `needs_review` 人工复核状态、优先级和稳定原因码；
- 原 OCR 接口、单文件分析、已有 OCR 再分析、材料包分析及批量校验 API；
- 请求体、文件、页数和计算资源的基础防护；
- 可选的原子 JSON 调试结果保存；
- CPU 优先、非 root 用户运行的 Dockerfile。

分类和字段提取使用透明、可审计的规则，不依赖训练数据。所有提取字段同时保留原文、标准值、单位、页码、坐标和置信度；出现不同候选值时不会静默覆盖。

## 3. 支持的文档类型

接口中的稳定类型值如下：

| 类型值 | 含义 |
|---|---|
| `project_basic_info` | 项目基本资料 |
| `insurance_application` | 投保申请材料 |
| `pv_module_datasheet` | 光伏组件技术资料 |
| `pv_module_nameplate` | 光伏组件铭牌 |
| `inverter_datasheet` | 逆变器技术资料 |
| `inverter_nameplate` | 逆变器铭牌 |
| `equipment_list` | 设备清单 |
| `purchase_contract` | 采购/购销合同 |
| `epc_contract` | EPC 总承包合同 |
| `construction_contract` | 施工合同 |
| `inspection_report` | 检测、检验或试验报告 |
| `acceptance_document` | 验收资料 |
| `other` | 暂时无法归类的材料 |

可以通过 `GET /api/v1/document-types` 获取当前枚举。

## 4. 目录结构

```text
ocr_information_extraction/
├─ app/
│  ├─ api/              FastAPI 路由
│  ├─ core/             配置、日志、异常和请求体限制
│  ├─ ocr/              统一 OCR 接口及 PaddleOCR 适配器
│  ├─ preprocessing/    图片和 PDF 安全预处理
│  ├─ extraction/       分类、字段提取、表格行提取和标准化
│  ├─ validation/       单文档及跨文档数据质量校验
│  ├─ schemas/          Pydantic 输入输出模型
│  ├─ services/         OCR 和完整分析流程编排
│  ├─ utils/            上传及调试结果保存工具
│  └─ main.py           应用入口
├─ tests/               不依赖真实 OCR 模型的自动化测试
├─ sample_data/         本地人工测试材料目录，不提交客户文件
├─ output/              可选调试结果目录，不提交运行结果
├─ .env.example         环境变量示例
├─ requirements.txt     运行和测试依赖
├─ Dockerfile           CPU 容器配置
└─ .dockerignore        防止敏感或庞大文件进入构建上下文
```

## 5. 当前系统的数据流

```text
上传文件
→ 扩展名、媒体类型、文件头、体积校验
→ 图片解码或 PDF 逐页渲染
→ PaddleOCR 识别文字、坐标和置信度
→ 文档级及页面级分类
→ 业务字段和设备表行提取
→ 日期、金额、数量、功率单位标准化
→ 单文档数据质量校验
→ 人工复核判断
→ 结构化 JSON
```

材料包接口会继续执行：

```text
多份单文档结果
→ 同一项目关键字段一致性校验
→ 材料包复核结论
```

OCR、字段提取和校验互相分离。未来更换云端 OCR 或企业内网 OCR 时，不需要把业务规则重写进 OCR 引擎。

## 6. 环境要求与 Windows 启动

- Windows 10/11 64 位；
- Python 3.11 64 位；
- CPU 满足 PaddlePaddle 的指令集要求；
- 首次安装依赖及下载官方 OCR 模型时可以联网；
- 建议预留数 GB 磁盘空间。

PowerShell 中依次执行：

```powershell
cd "D:\王锦程\Documents\ocr_information_extraction"

py -3.11 -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

Copy-Item .env.example .env
uvicorn app.main:app --reload
```

如果 `py -3.11` 找不到解释器，请先安装 64 位 Python 3.11。项目按 PaddlePaddle 3.3.1 CPU 版编写；未确认 CUDA、驱动和对应版本前，不要自行替换为 GPU 包。

PaddleOCR 延迟初始化：服务和健康检查启动时不会加载模型，第一次提交合法文件时才会创建模型，因此首个请求可能明显更慢。

启动后访问：

- Swagger：<http://127.0.0.1:8000/docs>
- 健康检查：<http://127.0.0.1:8000/health>

## 7. API 使用方法

### 只执行 OCR（兼容原接口）

```powershell
curl.exe -X POST "http://127.0.0.1:8000/api/v1/ocr" `
  -H "accept: application/json" `
  -F "file=@.\sample_data\test.png"
```

响应包含 `document`、`pages`、`text_blocks`、`full_text`、`processing_status` 和耗时。

### 完整分析单个文件

```powershell
curl.exe -X POST "http://127.0.0.1:8000/api/v1/analyze" `
  -H "accept: application/json" `
  -F "file=@.\sample_data\投保单.pdf"
```

除原始 OCR 外，响应还会包含：

- `classification`：文档类型、候选类别、命中关键词及逐页分类；
- `extracted_fields`：字段原文、标准值、单位、置信度和来源坐标；
- `equipment_items`：设备清单逐行结果；
- `validation_issues`：数据质量问题；
- `review`：是否需要人工复核、优先级及原因；
- `processing_status`：`success`、`needs_review` 或 `failed`。

`needs_review` 仅表示数据需要人工确认，不代表高风险、拒保或材料无效。

### 分析同一项目的一组材料

```powershell
curl.exe -X POST "http://127.0.0.1:8000/api/v1/analyze-package" `
  -H "accept: application/json" `
  -F "project_group_id=case-001" `
  -F "files=@.\sample_data\项目资料.pdf" `
  -F "files=@.\sample_data\投保单.pdf" `
  -F "files=@.\sample_data\设备清单.xlsx.pdf"
```

材料包至少 2 个文件。接口顺序处理每份材料，再返回单文档结果和 `consistency` 跨文档校验结果。

### 对已有 OCR JSON 重新提取

`POST /api/v1/analyze/from-ocr` 接收一个完整 `OCRDocumentResult` JSON，适合规则调整后重跑，不需要再次调用 PaddleOCR。

### 对已有分析 JSON 执行一致性校验

`POST /api/v1/validate/batch` 接收 2 至 100 个 `DocumentAnalysisResult`。只有确认材料属于同一项目时才应放在同一请求中比较。

## 8. 如何测试

自动化测试不加载或下载真实 OCR 模型：

```powershell
cd "D:\王锦程\Documents\ocr_information_extraction"
.\.venv\Scripts\Activate.ps1
python -m pytest -q
```

人工验收建议依次上传：

1. 一张清晰的中文 PNG/JPG，确认返回文字、置信度和四点坐标；
2. 一个至少两页的 PDF，确认每页 `page_number` 正确；
3. 一份带“项目名称、装机容量”等标签的项目资料，确认字段有标准值和来源坐标；
4. 一份设备清单，确认多行设备没有压成一个字段；
5. 两份同项目但容量故意不同的材料，确认材料包返回跨文档冲突；
6. 一份模糊或格式特殊的材料，确认系统返回 `needs_review`，而不是生成核保结论。

第一次真实 OCR 验收会下载模型。自动化测试通过不等于所有客户版式都能直接高准确率提取，真实材料仍需建立脱敏回归样本集。

## 9. 配置说明

复制 `.env.example` 为 `.env` 后可以调整：

| 配置 | 默认值 | 作用 |
|---|---:|---|
| `APP_NAME` | 中文项目名 | Swagger 服务名称 |
| `DEBUG` | `false` | 调试日志开关 |
| `OUTPUT_DIR` | `output` | 可选调试 JSON 目录 |
| `MAX_FILE_SIZE_MB` | `20` | 单文件最大体积 |
| `MAX_PDF_PAGES` | `50` | 单 PDF 最大页数 |
| `MAX_IMAGE_PIXELS` | `40000000` | 单图片/单渲染页最大像素数 |
| `MAX_PDF_TOTAL_PIXELS` | `200000000` | 一个 PDF 的总渲染像素上限 |
| `MAX_PACKAGE_FILES` | `20` | 一个材料包最多文件数 |
| `MAX_PACKAGE_SIZE_MB` | `100` | 材料包文件总体积上限 |
| `MAX_JSON_BODY_MB` | `25` | 再分析/批量校验 JSON 请求上限 |
| `MAX_CONCURRENT_OCR` | `1` | 单进程同时执行的 OCR 任务数 |
| `PDF_DPI` | `200` | PDF 渲染清晰度 |
| `OCR_LANGUAGE` | `ch` | OCR 语言 |
| `OCR_DEVICE` | `cpu` | 推理设备 |
| `OCR_ENABLE_MKLDNN` | `false` | Windows 默认关闭以提高兼容性 |
| `OCR_MODEL_CACHE_DIR` | 公共英文路径示例 | PaddleX 模型缓存目录 |
| `SAVE_RESULTS` | `false` | 是否保存调试分析 JSON |
| 三个 `*_REVIEW_THRESHOLD` | 见示例 | 分类、字段及 OCR 复核阈值 |

Windows 用户名或模型路径含中文时，PaddlePaddle 的底层推理库在部分环境会无法加载模型，所以示例使用纯英文缓存路径。`C:/Users/Public/paddlex-cache` 仅适合受控的本地开发；生产环境应改成服务账户专属、不可被普通用户修改的目录。

开启 `SAVE_RESULTS=true` 后，调试结果写入 `output/<document_id>/`。写入采用固定安全路径及原子替换，但这些 JSON 可能包含客户敏感信息；生产环境必须另行配置访问控制、磁盘加密、保留期限和定期删除。该开关是调试输出，不是数据库或业务归档系统。

## 10. Docker（CPU）

```powershell
cd "D:\王锦程\Documents\ocr_information_extraction"
docker build -t pv-ocr-extraction .
docker run --rm -p 8000:8000 pv-ocr-extraction
```

容器使用非 root 用户，并把模型缓存放在 `/app/.cache/paddlex`。首次请求仍可能下载模型；生产部署宜使用受控持久卷或在经过许可和完整性校验后预置模型。当前工作环境未安装 Docker，因此需要在有 Docker 的目标机器上再执行构建和冒烟测试。

## 11. 安全和部署注意事项

- 用户文件名仅作为响应元数据，不参与临时路径拼接；
- 同时校验扩展名、媒体类型、文件头及实际读取大小；
- 在 multipart/JSON 解析前按请求路径限制请求体；
- OCR 在有界工作线程中运行，不阻塞 FastAPI 事件循环；
- 大模型首次初始化加锁，单进程不会并发重复加载；
- 拒绝 NaN/Inf 坐标，并检查页码、页数和坐标范围；
- 日志不记录 OCR 全文或客户材料；
- `.env`、模型缓存、调试结果和本地测试材料不会进入 Docker 构建上下文。

本项目没有账号和复杂权限系统。对外部署时仍应放在具备 TLS、身份认证、访问控制、限流、请求超时及审计能力的 API 网关或反向代理之后；不要直接把开发模式服务暴露到公网。

## 12. 当前边界

已经完成的是可运行、可扩展、可审计的规则型 OCR 与信息提取基线。以下内容仍属于部署或持续准确率建设，而不是本仓库擅自承担的核保功能：

- 新客户版式需要通过脱敏样本补充关键词、字段别名和表格规则；
- 复杂跨页表格、合并单元格、手写件和严重倾斜/模糊材料可能进入人工复核；
- 真实生产吞吐量、CPU/内存、超时和模型缓存需在目标服务器压测；
- Docker 镜像和真实 PaddleOCR 需在目标容器环境做最终冒烟测试；
- 不包含前端、数据库、账号权限、人工复核操作台和任务队列；
- 不包含光伏照片风险识别、天气风险、核保评分、保险规则、保费或承保结论。

后续如需提高准确率，应优先收集脱敏真实材料建立 golden dataset，对分类、字段及表格规则做量化回归；不要把核保逻辑塞进 OCR 层。
