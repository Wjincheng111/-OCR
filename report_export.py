"""
PDF 导出模块

将生成的 Markdown 报告转换为 PDF 文件。
实现方式：解析本模块产出的 Markdown（标题/表格/列表/段落/分隔线/引用），
借助 reportlab 的 Platypus 流式排版生成 PDF，并优先使用系统中文字体。

若运行环境缺少 reportlab，则保留导出接口并抛出明确错误提示。
"""

import re
from pathlib import Path
from typing import List, Optional
from xml.sax.saxutils import escape

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import (
        HRFlowable,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    _REPORTLAB_AVAILABLE = True
except Exception:  # pragma: no cover - 依赖缺失场景
    _REPORTLAB_AVAILABLE = False

# 中文字体候选（Windows 常见字体；.ttc 需指定 subfontIndex=0）
_FONT_CANDIDATES = [
    (r"C:\Windows\Fonts\simhei.ttf", False),   # 黑体
    (r"C:\Windows\Fonts\Deng.ttf", False),      # 等线
    (r"C:\Windows\Fonts\simfang.ttf", False),   # 仿宋
    (r"C:\Windows\Fonts\simsun.ttc", True),     # 宋体（TTC）
    (r"C:\Windows\Fonts\msyh.ttc", True),       # 微软雅黑（TTC）
]

_REGISTERED_FONT = None


def is_pdf_supported() -> bool:
    """判断当前环境是否具备 PDF 导出能力"""
    return _REPORTLAB_AVAILABLE


def _register_cjk_font() -> str:
    """注册中文字体，返回注册后的字体名；失败时回退到内置 CID 字体"""
    global _REGISTERED_FONT
    if _REGISTERED_FONT:
        return _REGISTERED_FONT

    if _REPORTLAB_AVAILABLE:
        # 优先使用系统 TTF/TTC 字体（字体内嵌，PDF 可移植性好）
        for path, is_ttc in _FONT_CANDIDATES:
            try:
                if not Path(path).exists():
                    continue
                name = "CJK-" + Path(path).stem
                if is_ttc:
                    pdfmetrics.registerFont(TTFont(name, path, subfontIndex=0))
                else:
                    pdfmetrics.registerFont(TTFont(name, path))
                _REGISTERED_FONT = name
                return name
            except Exception:
                continue
        # 回退到 reportlab 内置 CID 中文字体（依赖 PDF 阅读器的字体替换）
        try:
            pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
            _REGISTERED_FONT = "STSong-Light"
            return _REGISTERED_FONT
        except Exception:
            pass

    _REGISTERED_FONT = "Helvetica"
    return _REGISTERED_FONT


def _inline(text: str) -> str:
    """转义 XML 特殊字符，并将 **加粗** 转换为 reportlab 加粗标签"""
    text = escape(str(text))
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    return text


def _build_styles(font_name: str) -> dict:
    """构建带中文支持的段落样式"""
    base = getSampleStyleSheet()
    normal = ParagraphStyle(
        "NormalCN", parent=base["Normal"], fontName=font_name,
        fontSize=10.5, leading=16, wordWrap="CJK",
    )
    h1 = ParagraphStyle(
        "H1CN", parent=base["Title"], fontName=font_name,
        fontSize=18, leading=24, spaceAfter=12, wordWrap="CJK",
    )
    h2 = ParagraphStyle(
        "H2CN", parent=base["Heading2"], fontName=font_name,
        fontSize=14, leading=20, spaceBefore=10, spaceAfter=6, wordWrap="CJK",
    )
    quote = ParagraphStyle(
        "QuoteCN", parent=normal, fontName=font_name,
        textColor=colors.HexColor("#666666"), leftIndent=10, fontSize=9.5, wordWrap="CJK",
    )
    bullet = ParagraphStyle(
        "BulletCN", parent=normal, fontName=font_name,
        leftIndent=16, bulletIndent=4, wordWrap="CJK",
    )
    cell = ParagraphStyle(
        "CellCN", fontName=font_name, fontSize=9, leading=12, wordWrap="CJK",
    )
    return {"normal": normal, "h1": h1, "h2": h2, "quote": quote, "bullet": bullet, "cell": cell}


def _parse_table(block: List[str]) -> List[List[str]]:
    """解析 Markdown 表格块，返回数据行（不含分隔行）"""
    rows = []
    for line in block:
        line = line.strip()
        if not line.startswith("|"):
            continue
        # 只按未转义的竖线切分，使“\|”可安全出现在单元格内容中。
        cells = [
            c.strip().replace(r"\|", "|")
            for c in re.split(r"(?<!\\)\|", line.strip().strip("|"))
        ]
        # 分隔行（如 | --- | --- |）跳过
        if all((set(c) <= set("-: ") and c) for c in cells):
            continue
        rows.append(cells)
    return rows


def _column_widths(column_count: int, available_width: float) -> List[float]:
    """按报告中常见表格结构分配列宽，减少宽表溢出页面。"""
    ratios = {
        2: (0.28, 0.72),
        4: (0.18, 0.15, 0.13, 0.54),
        5: (0.14, 0.12, 0.16, 0.20, 0.38),
    }.get(column_count)
    if ratios is None:
        ratios = tuple(1 / column_count for _ in range(column_count))
    return [available_width * ratio for ratio in ratios]


def markdown_to_pdf(
    markdown_text: str,
    output_path,
    title: Optional[str] = None,
) -> Path:
    """
    将 Markdown 报告转换为 PDF 文件。

    Args:
        markdown_text: Markdown 文本内容
        output_path: 输出 PDF 文件路径
        title: PDF 文档标题（可选）
    Returns:
        生成的 PDF 文件路径
    Raises:
        RuntimeError: 缺少 reportlab 依赖时抛出
    """
    if not _REPORTLAB_AVAILABLE:
        raise RuntimeError(
            "当前环境缺少 reportlab 依赖，无法导出 PDF。请执行：pip install reportlab"
        )

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    font_name = _register_cjk_font()
    styles = _build_styles(font_name)

    def _draw_footer(canvas, _doc):
        """在每页底部绘制页码"""
        canvas.saveState()
        try:
            canvas.setFont(font_name, 8)
        except Exception:
            canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#888888"))
        canvas.drawCentredString(A4[0] / 2, 12, "第 {} 页".format(canvas.getPageNumber()))
        canvas.restoreState()

    doc = SimpleDocTemplate(str(output_path), pagesize=A4, title=title or "核保评估报告")

    story = []
    lines = str(markdown_text).splitlines()
    i, n = 0, len(lines)
    while i < n:
        stripped = lines[i].strip()

        # 空行
        if not stripped:
            i += 1
            continue

        # 分隔线
        if set(stripped) <= {"-", " "} and stripped.count("-") >= 3:
            story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#999999")))
            story.append(Spacer(1, 6))
            i += 1
            continue

        # 标题
        if stripped.startswith("#"):
            level = len(stripped) - len(stripped.lstrip("#"))
            text = stripped.lstrip("#").strip()
            story.append(Paragraph(_inline(text), styles["h1"] if level == 1 else styles["h2"]))
            i += 1
            continue

        # 表格
        if stripped.startswith("|"):
            j = i
            while j < n and lines[j].strip().startswith("|"):
                j += 1
            rows = _parse_table(lines[i:j])
            if rows:
                data = [[Paragraph(_inline(c), styles["cell"]) for c in row] for row in rows]
                table = Table(
                    data,
                    colWidths=_column_widths(len(rows[0]), doc.width),
                    repeatRows=1,
                    splitByRow=1,
                    hAlign="LEFT",
                )
                table.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EEEEEE")),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CCCCCC")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]))
                story.append(table)
                story.append(Spacer(1, 8))
            i = j
            continue

        # 引用块
        if stripped.startswith(">"):
            story.append(Paragraph(_inline(stripped.lstrip(">").strip()), styles["quote"]))
            story.append(Spacer(1, 4))
            i += 1
            continue

        # 无序列表
        if stripped.startswith("- ") or stripped.startswith("* "):
            story.append(Paragraph(_inline(stripped[2:].strip()), styles["bullet"], bulletText="•"))
            i += 1
            continue

        # 普通段落
        story.append(Paragraph(_inline(stripped), styles["normal"]))
        story.append(Spacer(1, 4))
        i += 1

    doc.build(story, onFirstPage=_draw_footer, onLaterPages=_draw_footer)
    return output_path
