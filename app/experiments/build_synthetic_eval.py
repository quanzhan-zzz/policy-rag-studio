import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class SectionSpec:
    document_id: str
    heading: str
    subjects: tuple[str, str, str, str]
    focuses: tuple[str, str]
    failure_type: str


SECTION_SPECS: tuple[SectionSpec, ...] = (
    SectionSpec(
        "individual-registration",
        "一、事项名称",
        ("个体工商户设立登记", "个体工商户登记业务", "个体工商户营业执照办理", "个体工商户设立"),
        ("事项名称", "登记事项"),
        "事项名称语义召回失败",
    ),
    SectionSpec(
        "individual-registration",
        "二、申请条件",
        ("个体工商户登记", "个体工商户注册", "个体工商户营业执照申请", "个体工商户设立"),
        ("申请条件", "办理条件"),
        "申请条件召回失败",
    ),
    SectionSpec(
        "individual-registration",
        "三、申请材料",
        ("个体工商户设立登记", "个体工商户登记申请", "个体工商户营业执照办理", "个体工商户注册"),
        ("申请材料", "材料清单"),
        "材料清单召回不足",
    ),
    SectionSpec(
        "individual-registration",
        "四、办理流程",
        ("个体工商户设立登记", "个体工商户登记申请", "个体工商户营业执照办理", "个体工商户注册"),
        ("办理流程", "申请步骤"),
        "流程条款召回失败",
    ),
    SectionSpec(
        "individual-registration",
        "五、办理时限",
        ("个体工商户设立登记", "个体工商户变更登记", "个体工商户注销登记", "个体工商户登记补正"),
        ("办理时限", "审核期限"),
        "时限条款排名偏低",
    ),
    SectionSpec(
        "individual-registration",
        "六、注意事项",
        ("个体工商户登记", "个体工商户经营场所证明", "个体工商户身份证明", "个体工商户经营范围"),
        ("注意事项", "材料与经营场所要求"),
        "约束条款召回失败",
    ),
    SectionSpec(
        "individual-registration",
        "七、常见问题",
        (
            "个体工商户家庭成员共同经营",
            "个体工商户经营者变更",
            "个体工商户经营场所变更",
            "个体工商户终止经营",
        ),
        ("常见问题", "办理说明"),
        "常见问题召回失败",
    ),
    SectionSpec(
        "talent-housing-subsidy",
        "一、适用范围",
        ("青年人才租房补贴", "常州市青年人才租房补贴", "青年人才安居补贴", "租房补贴申请"),
        ("适用范围", "适用对象"),
        "适用范围语义召回失败",
    ),
    SectionSpec(
        "talent-housing-subsidy",
        "二、申报条件",
        ("青年人才租房补贴", "常州市青年人才租房补贴", "青年人才租房补助", "租房补贴申请"),
        ("申报条件", "申请资格"),
        "申报条件召回失败",
    ),
    SectionSpec(
        "talent-housing-subsidy",
        "三、补贴标准",
        ("青年人才租房补贴", "博士租房补贴", "硕士租房补贴", "本科毕业生租房补贴"),
        ("补贴标准", "发放标准"),
        "补贴标准召回失败",
    ),
    SectionSpec(
        "talent-housing-subsidy",
        "四、申报材料",
        ("青年人才租房补贴", "常州市青年人才租房补贴", "租房补贴申请", "人才安居补贴"),
        ("申报材料", "材料清单"),
        "补贴材料召回不足",
    ),
    SectionSpec(
        "talent-housing-subsidy",
        "五、动态管理",
        ("青年人才租房补贴", "租房补贴资格", "补贴期间工作单位变更", "补贴期间租房地址变更"),
        ("动态管理", "资格变化处理"),
        "动态管理召回失败",
    ),
    SectionSpec(
        "talent-housing-subsidy",
        "六、办理流程",
        ("青年人才租房补贴", "常州市青年人才租房补贴", "租房补贴申请", "人才安居补贴"),
        ("办理流程", "申请审核流程"),
        "补贴流程召回失败",
    ),
    SectionSpec(
        "business-license-change",
        "一、适用范围",
        ("企业营业执照变更登记", "企业名称变更登记", "企业住所变更登记", "企业法定代表人变更登记"),
        ("适用范围", "适用情形"),
        "变更适用范围召回失败",
    ),
    SectionSpec(
        "business-license-change",
        "二、办理流程",
        ("企业营业执照变更登记", "企业名称变更登记", "企业住所变更登记", "企业法定代表人变更登记"),
        ("办理流程", "变更步骤"),
        "变更流程召回失败",
    ),
    SectionSpec(
        "business-license-change",
        "三、申请材料",
        ("企业营业执照变更登记", "企业名称变更登记", "企业住所变更登记", "企业法定代表人变更登记"),
        ("申请材料", "材料清单"),
        "变更材料召回不足",
    ),
    SectionSpec(
        "business-license-change",
        "四、审核要点",
        ("企业营业执照变更登记", "企业名称变更登记", "企业住所变更登记", "企业法定代表人变更登记"),
        ("审核要点", "审核重点"),
        "审核要点召回失败",
    ),
    SectionSpec(
        "business-license-change",
        "五、办理时限",
        ("企业营业执照变更登记", "企业名称变更登记", "企业住所变更登记", "企业法定代表人变更登记"),
        ("办理时限", "审核期限"),
        "变更时限召回失败",
    ),
    SectionSpec(
        "business-license-change",
        "六、注意事项",
        ("企业营业执照变更登记", "企业名称变更登记", "企业住所变更登记", "企业法定代表人变更登记"),
        ("注意事项", "许可与电子签名要求"),
        "变更约束条款召回失败",
    ),
)

TEMPLATES = (
    "{subject}的{focus}是什么？",
    "请问{subject}在{focus}方面有哪些规定？",
)


def build_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for section_index, section in enumerate(SECTION_SPECS, start=1):
        pairs = (
            (section.subjects[0], section.focuses[0]),
            (section.subjects[1], section.focuses[0]),
            (section.subjects[2], section.focuses[1]),
            (section.subjects[3], section.focuses[1]),
        )
        variant = 0
        for subject, focus in pairs:
            for template in TEMPLATES:
                rows.append(
                    {
                        "id": f"synthetic-{section_index:02d}-{variant:02d}",
                        "query": template.format(subject=subject, focus=focus),
                        "expected_document_id": section.document_id,
                        "expected_heading": section.heading,
                        "failure_type": section.failure_type,
                        "split": "dev" if variant < 6 else "test",
                        "dataset": "policy-synthetic-v1",
                    }
                )
                variant += 1
    return rows


def main() -> None:
    output = Path("data/eval/policy-synthetic-v1.jsonl")
    output.parent.mkdir(parents=True, exist_ok=True)
    rows = build_rows()
    output.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n"
    )
    dev = sum(row["split"] == "dev" for row in rows)
    test = sum(row["split"] == "test" for row in rows)
    print(f"wrote {len(rows)} cases to {output} (dev={dev}, test={test})")


if __name__ == "__main__":
    main()
