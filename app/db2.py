"""DB2 导出表读取：把 5 张 CSV 组装成 classes → specs → assist_plan → steps → rules 嵌套结构。

数据流与旧版 ``src/wow_assist_mapper/skeleton.py`` 的 ``parse_and_build_db_dumps`` 保持一致：

- 归属关系（专精找职业、方案找专精、步骤找方案、规则找步骤）都是逐行扫描 + 反向查找；
- ``steps`` / ``rules`` 的字典键是 OrderIndex，但遍历顺序是 CSV 行插入顺序
  （本期不按 OrderIndex 排序，保持旧行为）；
- 旧版在这里为每个步骤技能联网抓取技能名，本模块不再做这件事，技能名由 ``app/spells.py`` 提供。
"""

import logging
import re

import pandas as pd

_logger = logging.getLogger(__name__)

# 5 张表统一使用旧版的读取参数：ChrSpecialization.Description_lang 含换行与逗号，
# 必须用 python 引擎才能正确合并多行字段。
CSV_READ_ARGS = {"quoting": 0, "engine": "python", "quotechar": '"'}


def table_filename(table_name, version):
    """拼出某张表的 CSV 文件名，例如 ``AssistedCombat.12.1.0.69814.csv``。"""
    return f"{table_name}.{version}.csv"


def read_table(csv_dir, table_name, version):
    """按旧版参数读取一张 CSV 表。"""
    return pd.read_csv(f"{csv_dir}/{table_filename(table_name, version)}", **CSV_READ_ARGS)


def parse_and_build_db_dumps(csv_dir, version):
    """读取 5 张表并构建嵌套结构，返回 ``classes`` 字典（顶层键 = ChrClasses.Name_lang）。"""
    chr_classes = read_table(csv_dir, "ChrClasses", version)
    chr_specs = read_table(csv_dir, "ChrSpecialization", version)
    assisted_combat = read_table(csv_dir, "AssistedCombat", version)
    assisted_combat_step = read_table(csv_dir, "AssistedCombatStep", version)
    assisted_combat_rule = read_table(csv_dir, "AssistedCombatRule", version)

    # 职业层：顶层键用 Name_lang（如 "Death Knight"），主键另存为 "ID"
    classes = {}
    for index, row in chr_classes.iterrows():
        _logger.info(f"Class Row {index}: {row.to_dict()}")
        classes[row["Name_lang"]] = {
            "raw_data": row.to_dict(),
            "ID": int(row["ID"]),
            "Name": row["Name_lang"],
            "specs": {},
        }

    # 专精层：按 ClassID 挂到对应职业下；ClassID 匹配不到职业的专精不会进入 classes
    specs = {}
    for index, row in chr_specs.iterrows():
        _logger.info(f"Spec Row {index}: {row.to_dict()}")
        spec_data = {
            "raw_data": row.to_dict(),
            "ID": int(row["ID"]),
            "Name": row["Name_lang"],
        }
        specs[row["ID"]] = spec_data
        for class_data in classes.values():
            if class_data["ID"] == row["ClassID"]:
                class_data["specs"][row["ID"]] = spec_data

    # 方案层：按 ChrSpecializationID 挂到专精下；只有 AssistedCombat 表里出现的专精才有 assist_plan
    assist_plans = {}
    for index, row in assisted_combat.iterrows():
        _logger.info(f"Assisted Combat Row {index}: {row.to_dict()}")
        plan_data = {"ID": int(row["ID"]), "steps": {}}
        assist_plans[int(row["ID"])] = plan_data
        for spec_data in specs.values():
            if spec_data["ID"] == row["ChrSpecializationID"]:
                spec_data["assist_plan"] = plan_data

    # 步骤层：按 AssistedCombatID 挂到方案下，键是 OrderIndex（同一步骤内重复键会覆盖）
    assist_steps = {}
    for index, row in assisted_combat_step.iterrows():
        _logger.info(f"Assisted Combat Step Row {index}: {row.to_dict()}")
        step_data = {
            "ID": int(row["ID"]),
            "SpellID": int(row["SpellID"]),
            "OrderIndex": int(row["OrderIndex"]),
            "rules": {},
        }
        assist_steps[int(row["ID"])] = step_data
        assist_plans[int(row["AssistedCombatID"])]["steps"][int(row["OrderIndex"])] = step_data

    # 规则层：按 AssistedCombatStepID 挂到步骤下；渲染只依赖 raw（CSV 原始行）
    for index, row in assisted_combat_rule.iterrows():
        _logger.info(f"Assisted Combat Rule Row {index}: {row.to_dict()}")
        if int(row["Field_11_1_7_60520_002"]) != 0:
            # 该字段含义未明，保留旧版"非 0 时告警"的观察点
            _logger.warning(f"Field Field_11_1_7_60520_002 is non-zero: {row['Field_11_1_7_60520_002']}")
            _logger.warning(row.to_dict())
        rule_data = {
            "ID": int(row["ID"]),
            "OrderIndex": int(row["OrderIndex"]),
            "raw": row.to_dict(),
        }
        assist_steps[int(row["AssistedCombatStepID"])]["rules"][int(row["OrderIndex"])] = rule_data

    return classes


def iter_specs_with_plan(classes):
    """按类表/专精表的 CSV 行顺序产出 ``(职业显示名, 专精数据)``，只含有辅助方案的专精。

    这是新版"专精查找"的入口：main.py 据此逐个专精渲染，替代旧版按 CLI 名称查找。
    """
    for class_name, class_data in classes.items():
        for spec_data in class_data["specs"].values():
            if spec_data.get("assist_plan"):
                yield class_name, spec_data


def find_spec(classes, class_name, spec_name):
    """按显示名查找专精（保留旧版 find_rotation 的名称匹配语义）；找不到返回 None。

    兼容旧版 CLI 的 CamelCase 写法：``DeathKnight`` / ``BeastMastery`` 会先按旧版正则
    还原成 CSV 里的显示名 ``Death Knight`` / ``Beast Mastery`` 再比较，因此
    ``find_spec(classes, "DeathKnight", "BeastMastery")`` 与
    ``find_spec(classes, "Death Knight", "Beast Mastery")`` 都能命中。
    匹配范围限定在指定职业内，因此 Paladin / Priest 各自的 "Holy" 不会混淆。
    """
    class_data = _find_class(classes, class_name)
    if not class_data:
        return None
    for spec_data in class_data["specs"].values():
        if _name_matches(spec_data["Name"], spec_name):
            return spec_data
    return None


def _find_class(classes, class_name):
    """按显示名或 CamelCase 写法找职业数据。"""
    for class_key, class_data in classes.items():
        if _name_matches(class_key, class_name):
            return class_data
    return None


def _name_matches(display_name, query):
    """显示名与查询名匹配：原样相等，或查询名是 CamelCase 还原后的写法。"""
    return query == display_name or _restore_display_name(query) == display_name


def _restore_display_name(name):
    """把 CamelCase 写法还原成 CSV 里的显示名（旧版正则），并合并多余空格。

    ``DeathKnight`` → ``Death Knight``；本身就是 ``Death Knight`` 的输入会被正则
    在 K 前再插一个空格，因此这里把连续空格合并成一个，保证两种写法都能匹配。
    """
    spaced = re.sub(r"(?<!^)(?=[A-Z])", " ", name)
    return re.sub(r"\s+", " ", spaced).strip()


def spec_rotation(spec_data):
    """取某专精方案的全部步骤（list），顺序 = steps 字典插入顺序 = CSV 行顺序。"""
    plan = spec_data.get("assist_plan")
    if not plan:
        return []
    return list(plan.get("steps", {}).values())


def iter_plan_steps(classes):
    """遍历全部方案的全部步骤（收集技能 ID 用），顺序同 :func:`iter_specs_with_plan`。"""
    for _class_name, spec_data in iter_specs_with_plan(classes):
        yield from spec_rotation(spec_data)
