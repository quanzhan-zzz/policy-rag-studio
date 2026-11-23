import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OFFICIAL_GUIDES_PATH = ROOT / "data" / "official" / "jszwfw-guides.v1.jsonl"


@dataclass(frozen=True, slots=True)
class SeedDocument:
    id: str
    title: str
    department: str
    effective_date: str
    tags: tuple[str, ...]
    text: str
    source_name: str | None = None
    source_url: str | None = None
    source_retrieved_at: datetime | None = None
    source_sha256: str | None = None


SEED_DOCUMENTS: tuple[SeedDocument, ...] = (
    SeedDocument(
        id="individual-registration",
        title="个体工商户登记办事指南（演示）",
        department="常州市政务服务管理办公室",
        effective_date="2026-01-01",
        tags=("登记", "个体工商户", "申报"),
        text="""# 个体工商户登记办事指南（演示）

一、事项名称
个体工商户设立登记。

二、申请条件
申请人应具有完全民事行为能力，有固定的经营场所，并依法提交真实、完整、有效的申请材料。经营范围涉及许可项目的，应先取得相应许可。

三、申请材料
1. 个体工商户登记（备案）申请书；
2. 经营者身份证明；
3. 经营场所使用证明；
4. 委托办理的，提交授权委托书和代理人身份证明；
5. 涉及许可经营项目的，提交相关许可证件。

四、办理流程
申请人在线填报信息并上传材料，系统进行材料完整性预检。预检通过后提交至登记机关审核，审核通过后生成电子营业执照。材料不齐全的，登记机关一次性告知需要补正的内容。

五、办理时限
材料齐全且符合法定形式的，登记机关在三个工作日内办结。需要补正材料的，办理时限自补正材料提交之日起重新计算。

六、注意事项
经营场所证明应包含详细地址和使用权说明。身份证明应清晰完整。经营范围应按照登记规范表述，不得使用模糊或超出许可范围的表述。

七、常见问题
个体工商户可以由家庭成员共同经营。变更经营者、经营场所或经营范围的，应依法办理变更登记。终止经营的，应办理注销登记。
""",
    ),
    SeedDocument(
        id="talent-housing-subsidy",
        title="青年人才租房补贴实施办法（演示）",
        department="常州市人才工作领导小组办公室",
        effective_date="2025-07-01",
        tags=("人才", "补贴", "租房"),
        text="""# 青年人才租房补贴实施办法（演示）

一、适用范围
本办法适用于在常州市就业创业、符合青年人才认定条件并自行租房居住的人员。

二、申报条件
1. 与本市用人单位签订一年以上劳动合同并依法缴纳社会保险；
2. 在本市无自有住房，且未享受其他住房保障政策；
3. 年龄、学历或职业技能等级符合当年度青年人才认定标准；
4. 租赁住房应具有合法权属证明，租赁合同真实有效。

三、补贴标准
博士研究生、硕士研究生、本科毕业生和高级技师按照不同标准发放租房补贴。具体金额以当年度公布标准为准，补贴按月计算、按季度发放。

四、申报材料
申请人应提交人才认定材料、劳动合同、社会保险缴纳记录、无房证明、租赁合同和本人银行卡信息。系统可以通过数据共享获取的材料，不再要求申请人重复提交。

五、动态管理
补贴期间变更工作单位、租赁地址或婚姻状况的，应及时更新信息。不再符合条件或提供虚假材料的，停止发放并依法追回已发放补贴。

六、办理流程
申请人在线提交申请，人社部门进行资格审核，住房管理部门核验住房情况。审核结果公示后，按规定发放补贴。
""",
    ),
    SeedDocument(
        id="business-license-change",
        title="企业营业执照变更登记指引（演示）",
        department="常州市市场监督管理局",
        effective_date="2026-03-01",
        tags=("营业执照", "变更", "企业"),
        text="""# 企业营业执照变更登记指引（演示）

一、适用范围
企业名称、住所、法定代表人、注册资本、经营范围等登记事项发生变化的，应依法申请变更登记。

二、办理流程
申请人登录企业登记平台，选择变更事项，填写变更信息并上传材料。系统生成申请文书后，相关人员完成电子签名并提交。登记机关审核通过后换发营业执照。

三、申请材料
1. 企业变更登记申请书；
2. 股东会决议或者股东决定；
3. 修改后的公司章程或者章程修正案；
4. 新任法定代表人的任职文件和身份证明；
5. 住所变更的，提交新住所使用证明；
6. 名称变更的，提交名称自主申报材料。

四、审核要点
登记机关重点核对申请材料是否齐全、签字主体是否适格、变更事项是否履行内部决策程序、章程内容是否与变更事项一致。

五、办理时限
材料齐全且符合法定形式的，登记机关在一个工作日内完成变更登记。需要补正材料的，申请人应根据补正通知一次性补齐。

六、注意事项
变更登记事项涉及许可经营的，应先取得相关许可或者同步办理许可变更。电子签名应由本人完成，不得由他人代为签署。
""",
    ),
)


@dataclass(frozen=True, slots=True)
class EvaluationCase:
    id: str
    query: str
    expected_document_id: str
    expected_heading: str
    failure_type: str
    split: str = "smoke"


EVALUATION_CASES: tuple[EvaluationCase, ...] = (
    EvaluationCase(
        "eval-01",
        "个体工商户登记需要准备哪些申请材料",
        "individual-registration",
        "三、申请材料",
        "材料清单召回不足",
    ),
    EvaluationCase(
        "eval-02",
        "个体工商户多久能办完",
        "individual-registration",
        "五、办理时限",
        "时限条款排名偏低",
    ),
    EvaluationCase(
        "eval-03",
        "没有固定经营场所可以申请个体工商户吗",
        "individual-registration",
        "二、申请条件",
        "同义表达召回失败",
    ),
    EvaluationCase(
        "eval-04",
        "青年人才租房补贴的申报条件是什么",
        "talent-housing-subsidy",
        "二、申报条件",
        "条件条款召回失败",
    ),
    EvaluationCase(
        "eval-05",
        "硕士租房补贴每月多少钱",
        "talent-housing-subsidy",
        "三、补贴标准",
        "金额相关语义召回不足",
    ),
    EvaluationCase(
        "eval-06",
        "换工作以后人才补贴要更新吗",
        "talent-housing-subsidy",
        "五、动态管理",
        "口语化查询召回不足",
    ),
    EvaluationCase(
        "eval-07",
        "企业名称变更要提交哪些材料",
        "business-license-change",
        "三、申请材料",
        "精确条款匹配不足",
    ),
    EvaluationCase(
        "eval-08",
        "营业执照变更多久办结",
        "business-license-change",
        "五、办理时限",
        "时限信息排序偏低",
    ),
    EvaluationCase(
        "eval-09",
        "营业执照变更需要股东会决议吗",
        "business-license-change",
        "三、申请材料",
        "材料语义召回不足",
    ),
    EvaluationCase(
        "eval-10",
        "个体工商户经营范围有许可项目怎么办",
        "individual-registration",
        "二、申请条件",
        "条件跳转召回失败",
    ),
)


@lru_cache
def load_official_documents() -> tuple[SeedDocument, ...]:
    if not OFFICIAL_GUIDES_PATH.exists():
        raise FileNotFoundError(f"官方指南语料不存在：{OFFICIAL_GUIDES_PATH}")
    documents: list[SeedDocument] = []
    for line in OFFICIAL_GUIDES_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        text = str(row["text"])
        expected_text_hash = str(row["text_sha256"])
        actual_text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if actual_text_hash != expected_text_hash:
            raise ValueError(f"官方指南正文哈希不匹配：{row['id']}")
        source_url = str(row["source_url"])
        if not source_url.startswith("https://"):
            raise ValueError(f"官方指南来源必须使用 HTTPS：{row['id']}")
        retrieved_at = datetime.fromisoformat(
            str(row["source_retrieved_at"]).replace("Z", "+00:00")
        )
        tags = tuple(dict.fromkeys(str(tag) for tag in row.get("tags", [])))
        documents.append(
            SeedDocument(
                id=str(row["id"]),
                title=str(row["title"]),
                department=str(row["department"]),
                effective_date="未提供",
                tags=tags,
                text=text,
                source_name=str(row["source_name"]),
                source_url=source_url,
                source_retrieved_at=retrieved_at,
                source_sha256=str(row["source_pdf_sha256"]),
            )
        )
    identifiers = [document.id for document in documents]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("官方指南语料包含重复 ID")
    return tuple(documents)


def get_seed_documents(
    *,
    include_demo: bool = True,
    include_official: bool = True,
) -> tuple[SeedDocument, ...]:
    documents: list[SeedDocument] = []
    if include_demo:
        documents.extend(SEED_DOCUMENTS)
    if include_official:
        documents.extend(load_official_documents())
    identifiers = [document.id for document in documents]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("种子语料包含重复 ID")
    return tuple(documents)
