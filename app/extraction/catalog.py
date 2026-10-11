from dataclasses import dataclass

from app.schemas.classification import DocumentType


@dataclass(frozen=True)
class ClassificationRule:
    document_type: DocumentType
    keywords: tuple[tuple[str, float], ...]


@dataclass(frozen=True)
class FieldRule:
    field_name: str
    display_name: str
    patterns: tuple[str, ...]
    labels: tuple[str, ...]
    normalizer: str = "string"
    allowed_types: frozenset[DocumentType] | None = None


CLASSIFICATION_RULES: tuple[ClassificationRule, ...] = (
    ClassificationRule(
        DocumentType.INSURANCE_APPLICATION,
        (
            ("投保单", 7),
            ("财产险投保单", 9),
            ("投保申请", 7),
            ("投保人", 2),
            ("被保险人", 2),
            ("保险标的", 3),
            ("保险金额", 2),
        ),
    ),
    ClassificationRule(
        DocumentType.PV_MODULE_NAMEPLATE,
        (
            ("组件铭牌", 8),
            ("module nameplate", 8),
            ("photovoltaic module", 4),
            ("pv module", 3),
            ("maximum power", 2),
            ("pmax", 2),
            ("open circuit voltage", 2),
            ("short circuit current", 2),
        ),
    ),
    ClassificationRule(
        DocumentType.PV_MODULE_DATASHEET,
        (
            ("组件技术资料", 8),
            ("组件技术规格", 7),
            ("光伏组件规格书", 8),
            ("module datasheet", 8),
            ("电性能参数", 3),
            ("mechanical characteristics", 3),
            ("功率公差", 2),
        ),
    ),
    ClassificationRule(
        DocumentType.INVERTER_NAMEPLATE,
        (
            ("逆变器铭牌", 8),
            ("inverter nameplate", 8),
            ("rated output power", 3),
            ("最大输入电压", 2),
            ("mppt", 1),
            ("逆变器", 2),
        ),
    ),
    ClassificationRule(
        DocumentType.INVERTER_DATASHEET,
        (
            ("逆变器技术资料", 8),
            ("逆变器技术规格", 7),
            ("inverter datasheet", 8),
            ("逆变器规格书", 8),
            ("技术参数", 2),
            ("最大效率", 2),
            ("mppt", 1),
        ),
    ),
    ClassificationRule(
        DocumentType.EQUIPMENT_LIST,
        (
            ("设备清单", 8),
            ("供货清单", 7),
            ("主要设备表", 7),
            ("材料设备表", 7),
            ("设备名称", 3),
            ("序号", 1),
            ("数量", 1),
            ("单位", 1),
        ),
    ),
    ClassificationRule(
        DocumentType.PURCHASE_CONTRACT,
        (
            ("采购合同", 9),
            ("购销合同", 8),
            ("供货合同", 7),
            ("设备买卖合同", 8),
            ("买方", 2),
            ("卖方", 2),
            ("采购", 2),
        ),
    ),
    ClassificationRule(
        DocumentType.EPC_CONTRACT,
        (
            ("epc合同", 9),
            ("epc总承包合同", 10),
            ("epc contract", 9),
            ("工程总承包合同", 9),
            ("设计采购施工总承包合同", 10),
            ("设计采购施工", 6),
            ("发包人", 2),
            ("承包人", 2),
        ),
    ),
    ClassificationRule(
        DocumentType.CONSTRUCTION_CONTRACT,
        (
            ("施工合同", 9),
            ("建设工程施工", 8),
            ("施工单位", 3),
            ("开工日期", 2),
            ("竣工日期", 2),
        ),
    ),
    ClassificationRule(
        DocumentType.INSPECTION_REPORT,
        (
            ("检测报告", 9),
            ("检验报告", 8),
            ("测试报告", 7),
            ("试验报告", 7),
            ("型式试验报告", 9),
            ("检测结论", 4),
            ("检验结论", 4),
        ),
    ),
    ClassificationRule(
        DocumentType.ACCEPTANCE_DOCUMENT,
        (
            ("验收报告", 9),
            ("验收资料", 8),
            ("竣工验收", 8),
            ("并网验收", 8),
            ("验收记录", 7),
            ("验收结论", 4),
            ("验收日期", 2),
        ),
    ),
    ClassificationRule(
        DocumentType.PROJECT_BASIC_INFO,
        (
            ("项目基本资料", 9),
            ("项目基本情况", 9),
            ("项目概况", 7),
            ("项目简介", 7),
            ("项目备案信息", 8),
            ("项目名称", 2),
            ("装机容量", 3),
            ("建设地点", 2),
            ("并网容量", 2),
        ),
    ),
)


CONTRACT_TYPES = frozenset(
    {
        DocumentType.PURCHASE_CONTRACT,
        DocumentType.EPC_CONTRACT,
        DocumentType.CONSTRUCTION_CONTRACT,
    }
)
INSURANCE_TYPES = frozenset({DocumentType.INSURANCE_APPLICATION})
INSPECTION_TYPES = frozenset({DocumentType.INSPECTION_REPORT})


FIELD_RULES: tuple[FieldRule, ...] = (
    FieldRule(
        "document_number",
        "文件编号",
        (
            r"(?:文件编号|文档编号|编号)\s*[:：]\s*(?P<value>[A-Za-z0-9][A-Za-z0-9._/\-]{2,100})",
        ),
        ("文件编号", "文档编号", "编号"),
        "identifier",
    ),
    FieldRule(
        "project_name",
        "项目名称",
        (r"(?:项目名称|工程名称|项目名)\s*[:：]\s*(?P<value>[^\n]{2,120})",),
        ("项目名称", "工程名称", "项目名"),
    ),
    FieldRule(
        "project_location",
        "项目地点",
        (r"(?:项目地点|建设地点|项目地址|建设地址)\s*[:：]\s*(?P<value>[^\n]{2,160})",),
        ("项目地点", "建设地点", "项目地址", "建设地址"),
    ),
    FieldRule(
        "risk_location",
        "保险标的地址",
        (
            r"(?:保险标的地址|标的地址|风险地址)\s*[:：]\s*(?P<value>[^\n]{2,160})",
        ),
        ("保险标的地址", "标的地址", "风险地址"),
        allowed_types=INSURANCE_TYPES,
    ),
    FieldRule(
        "project_capacity_kw",
        "项目容量",
        (
            r"(?:装机容量|项目容量|总容量|并网容量)\s*[:：]\s*(?P<value>[\d,.]+\s*(?:MWp?|kWp?|kW|W|兆瓦|千瓦|瓦))",
        ),
        ("装机容量", "项目容量", "总容量", "并网容量"),
        "capacity_kw",
    ),
    FieldRule(
        "applicant_name",
        "投保人",
        (r"(?:投保人(?:名称)?|申请人)\s*[:：]\s*(?P<value>[^\n]{2,120})",),
        ("投保人", "投保人名称", "申请人"),
    ),
    FieldRule(
        "insured_name",
        "被保险人",
        (r"被保险人(?:名称)?\s*[:：]\s*(?P<value>[^\n]{2,120})",),
        ("被保险人", "被保险人名称"),
    ),
    FieldRule(
        "insurance_amount_cny",
        "保险金额",
        (
            r"(?:保险金额|投保金额|保险价值)\s*[:：]\s*(?P<value>(?:人民币|￥|¥)?\s*[\d,.]+\s*(?:亿元|万元|元)?)",
        ),
        ("保险金额", "投保金额", "保险价值"),
        "money_cny",
        INSURANCE_TYPES,
    ),
    FieldRule(
        "insurance_period_start",
        "保险期间开始日期",
        (
            r"(?:保险期间(?:自)?|保险起期|起保日期)\s*[:：]?\s*(?P<value>\d{4}[年./\-]\d{1,2}[月./\-]\d{1,2}日?)",
        ),
        ("保险期间", "保险期间自", "保险起期", "起保日期"),
        "date",
        INSURANCE_TYPES,
    ),
    FieldRule(
        "insurance_period_end",
        "保险期间结束日期",
        (
            r"(?:保险止期|终保日期|至)\s*[:：]?\s*(?P<value>\d{4}[年./\-]\d{1,2}[月./\-]\d{1,2}日?)",
        ),
        ("保险止期", "终保日期", "至"),
        "date",
        INSURANCE_TYPES,
    ),
    FieldRule(
        "project_owner",
        "建设/业主单位",
        (r"(?:建设单位|业主单位|项目业主|发包人)\s*[:：]\s*(?P<value>[^\n]{2,120})",),
        ("建设单位", "业主单位", "项目业主", "发包人"),
    ),
    FieldRule(
        "manufacturer",
        "制造商",
        (
            r"(?:制造商|生产厂家|制造厂家|manufacturer)\s*[:：]\s*(?P<value>[^\n]{2,120})",
        ),
        ("制造商", "生产厂家", "制造厂家", "manufacturer"),
    ),
    FieldRule(
        "brand",
        "品牌",
        (r"(?:品牌|brand)\s*[:：]\s*(?P<value>[^\n]{1,80})",),
        ("品牌", "brand"),
    ),
    FieldRule(
        "model",
        "设备型号",
        (
            r"(?:组件型号|逆变器型号|产品型号|设备型号|型号|model(?:\s*no\.?)?)\s*[:：]\s*(?P<value>[A-Za-z0-9][A-Za-z0-9._/\-+ ]{1,100})",
        ),
        ("组件型号", "逆变器型号", "产品型号", "设备型号", "型号", "model", "model no."),
        "identifier",
    ),
    FieldRule(
        "serial_number",
        "序列号",
        (
            r"(?:序列号|出厂编号|产品编号|serial\s*(?:no\.?|number)|s/n)\s*[:：]\s*(?P<value>[A-Za-z0-9][A-Za-z0-9._/\-]{2,100})",
        ),
        ("序列号", "出厂编号", "产品编号", "serial no.", "serial number", "s/n"),
        "identifier",
    ),
    FieldRule(
        "rated_power_w",
        "额定/最大功率",
        (
            r"(?:额定功率|最大功率|峰值功率|maximum\s+power|rated\s+(?:output\s+)?power|pmax)\s*[:：]?\s*(?P<value>[\d,.]+\s*(?:MW|kW|W|兆瓦|千瓦|瓦))",
        ),
        ("额定功率", "最大功率", "峰值功率", "maximum power", "rated power", "rated output power", "pmax"),
        "power_w",
    ),
    FieldRule(
        "module_count",
        "组件数量",
        (r"(?:组件数量|组件块数)\s*[:：]\s*(?P<value>[\d,]+\s*(?:块|片|件)?)",),
        ("组件数量", "组件块数"),
        "integer",
    ),
    FieldRule(
        "inverter_count",
        "逆变器数量",
        (r"逆变器数量\s*[:：]\s*(?P<value>[\d,]+\s*(?:台|套)?)",),
        ("逆变器数量",),
        "integer",
    ),
    FieldRule(
        "quantity",
        "数量",
        (r"(?:数量|qty|quantity)\s*[:：]\s*(?P<value>[\d,]+\s*(?:台|套|块|片|件)?)",),
        ("数量", "qty", "quantity"),
        "integer",
        frozenset({DocumentType.EQUIPMENT_LIST}),
    ),
    FieldRule(
        "contract_number",
        "合同编号",
        (r"(?:合同编号|合同号|contract\s*no\.?)\s*[:：]\s*(?P<value>[A-Za-z0-9][A-Za-z0-9._/\-]{2,100})",),
        ("合同编号", "合同号", "contract no."),
        "identifier",
        CONTRACT_TYPES,
    ),
    FieldRule(
        "contract_amount_cny",
        "合同金额",
        (
            r"(?:合同金额|合同总价|含税总价|总价|amount)\s*[:：]\s*(?P<value>(?:人民币|￥|¥)?\s*[\d,.]+\s*(?:亿元|万元|元)?)",
        ),
        ("合同金额", "合同总价", "含税总价", "总价", "amount"),
        "money_cny",
        CONTRACT_TYPES,
    ),
    FieldRule(
        "contract_date",
        "合同日期",
        (r"(?:签订日期|合同日期|签约日期)\s*[:：]\s*(?P<value>\d{4}[年./\-]\d{1,2}[月./\-]\d{1,2}日?)",),
        ("签订日期", "合同日期", "签约日期"),
        "date",
        CONTRACT_TYPES,
    ),
    FieldRule(
        "contract_scope",
        "合同范围",
        (r"(?:合同范围|工程范围|供货范围)\s*[:：]\s*(?P<value>[^\n]{2,240})",),
        ("合同范围", "工程范围", "供货范围"),
        allowed_types=CONTRACT_TYPES,
    ),
    FieldRule(
        "buyer_name",
        "买方/甲方",
        (r"(?:买方|甲方)\s*[:：]\s*(?P<value>[^\n]{2,120})",),
        ("买方", "甲方"),
        allowed_types=CONTRACT_TYPES,
    ),
    FieldRule(
        "seller_name",
        "卖方/乙方",
        (r"(?:卖方|乙方)\s*[:：]\s*(?P<value>[^\n]{2,120})",),
        ("卖方", "乙方"),
        allowed_types=CONTRACT_TYPES,
    ),
    FieldRule(
        "supplier_name",
        "供应商",
        (r"(?:供应商|供货方)\s*[:：]\s*(?P<value>[^\n]{2,120})",),
        ("供应商", "供货方"),
    ),
    FieldRule(
        "contractor_name",
        "承包/施工单位",
        (r"(?:承包人|承包单位|施工单位|EPC承包商)\s*[:：]\s*(?P<value>[^\n]{2,120})",),
        ("承包人", "承包单位", "施工单位", "EPC承包商"),
    ),
    FieldRule(
        "report_number",
        "报告编号",
        (
            r"(?:报告编号|检验编号|检测编号|report\s*no\.?)\s*[:：]\s*(?P<value>[A-Za-z0-9][A-Za-z0-9._/\-]{2,100})",
        ),
        ("报告编号", "检验编号", "检测编号", "report no."),
        "identifier",
        INSPECTION_TYPES,
    ),
    FieldRule(
        "testing_body",
        "检测机构",
        (r"(?:检测机构|检验机构|检测单位)\s*[:：]\s*(?P<value>[^\n]{2,120})",),
        ("检测机构", "检验机构", "检测单位"),
        allowed_types=INSPECTION_TYPES,
    ),
    FieldRule(
        "inspection_date",
        "检测日期",
        (r"(?:检测日期|检验日期|试验日期)\s*[:：]\s*(?P<value>\d{4}[年./\-]\d{1,2}[月./\-]\d{1,2}日?)",),
        ("检测日期", "检验日期", "试验日期"),
        "date",
        INSPECTION_TYPES,
    ),
    FieldRule(
        "inspection_conclusion",
        "检测结论",
        (r"(?:检测结论|检验结论|测试结论)\s*[:：]\s*(?P<value>[^\n]{1,240})",),
        ("检测结论", "检验结论", "测试结论"),
        "conclusion",
        frozenset({DocumentType.INSPECTION_REPORT}),
    ),
    FieldRule(
        "acceptance_conclusion",
        "验收结论",
        (r"验收结论\s*[:：]\s*(?P<value>[^\n]{1,240})",),
        ("验收结论",),
        "conclusion",
        frozenset({DocumentType.ACCEPTANCE_DOCUMENT}),
    ),
    FieldRule(
        "acceptance_date",
        "验收日期",
        (r"(?:验收日期|竣工验收日期)\s*[:：]\s*(?P<value>\d{4}[年./\-]\d{1,2}[月./\-]\d{1,2}日?)",),
        ("验收日期", "竣工验收日期"),
        "date",
        frozenset({DocumentType.ACCEPTANCE_DOCUMENT}),
    ),
)


REQUIRED_FIELDS: dict[DocumentType, tuple[str, ...]] = {
    DocumentType.PROJECT_BASIC_INFO: (
        "project_name",
        "project_location",
        "project_owner",
        "project_capacity_kw",
    ),
    DocumentType.INSURANCE_APPLICATION: (
        "applicant_name",
        "insured_name",
        "project_name",
        "risk_location",
        "insurance_amount_cny",
        "insurance_period_start",
        "insurance_period_end",
    ),
    DocumentType.PV_MODULE_DATASHEET: ("manufacturer", "model", "rated_power_w"),
    DocumentType.PV_MODULE_NAMEPLATE: (
        "manufacturer",
        "model",
        "rated_power_w",
        "serial_number",
    ),
    DocumentType.INVERTER_DATASHEET: ("manufacturer", "model", "rated_power_w"),
    DocumentType.INVERTER_NAMEPLATE: (
        "manufacturer",
        "model",
        "rated_power_w",
        "serial_number",
    ),
    DocumentType.EQUIPMENT_LIST: (),
    DocumentType.PURCHASE_CONTRACT: ("contract_number", "buyer_name", "seller_name"),
    DocumentType.EPC_CONTRACT: ("contract_number", "contractor_name"),
    DocumentType.CONSTRUCTION_CONTRACT: ("contract_number", "contractor_name"),
    DocumentType.INSPECTION_REPORT: (
        "report_number",
        "testing_body",
        "inspection_conclusion",
    ),
    DocumentType.ACCEPTANCE_DOCUMENT: (
        "project_name",
        "acceptance_date",
        "acceptance_conclusion",
    ),
}


FIELD_DISPLAY_NAMES = {rule.field_name: rule.display_name for rule in FIELD_RULES}
