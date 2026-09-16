"""条件渲染：加载 ConditionTypeMap.csv，把规则渲染成 4 空格缩进的可读文本行。

沿用旧版实现的两个关键点：

1. 模板用 ``eval('f"…"')`` 渲染，模板里可用的变量是 ``spell`` / ``arg1`` / ``arg2`` / ``arg3``。
   限制只存在于**模板侧**（``Description`` 列）：不能含双引号（会截断 f-string 字面量）、
   反斜杠（会被当转义），``{`` ``}`` 只能是设计好的占位符；技能名与条件值是作为变量值
   插入的，含撇号等任意字符都安全（如 ``'The Emperor's Capacitor'``）。
2. ``ValueN`` 列以 "spell"（不分大小写）开头时，``ConditionValueN`` 先解析为技能名再加单引号；
   技能名找不到时使用 ``Unknown Spell (ID)`` 占位（旧版会在这里崩）。

与旧版的差异（第一期确认的修正之一）：映射表未覆盖的条件类型不再抛 ``IndexError``，
而是抛出带 ConditionType 与规则 ID 的 ``ValueError``，便于定位缺失的映射行。
"""

import pandas as pd

# 与 db2 模块一致的 CSV 读取参数
CSV_READ_ARGS = {"quoting": 0, "engine": "python", "quotechar": '"'}

# 条件行固定缩进，旧版为 4 空格
INDENT = "    "


def load_condition_map(path):
    """读取条件类型映射表（参数与旧版一致）。"""
    return pd.read_csv(path, **CSV_READ_ARGS)


def condition_props(condition_map, condition_type, rule_id):
    """取出某条件类型对应的映射行；缺失时抛出明确错误，提示需要补充映射。"""
    props = condition_map[condition_map["Type"] == condition_type]
    if props.empty:
        raise ValueError(
            f"条件类型 ConditionType={condition_type} 未在 ConditionTypeMap.csv 中映射"
            f"（规则 ID={rule_id}）；请先补充该类型的说明行再重新运行"
        )
    return props.iloc[0]


def render_rule(condition_map, rule, spell_name, spell_index):
    """渲染一条规则为一行文本（含 4 空格缩进）。

    ``rule`` 是嵌套结构里的规则条目（用 ``raw`` 取条件值、用 ``ID`` 报错）；
    ``spell_name`` 是当前步骤的技能显示名；``spell_index`` 用于解析 Spell 型参数。
    """
    raw = rule["raw"]
    condition_type = raw.get("ConditionType")
    props = condition_props(condition_map, condition_type, rule.get("ID"))

    # 模板变量：spell 是当前步骤技能名；arg1..arg3 是条件值（Spell 型列已解析为带引号的技能名）
    spell = f"'{spell_name}'"
    arg1 = _resolve_value(raw, props, "1", spell_index)
    arg2 = _resolve_value(raw, props, "2", spell_index)
    arg3 = _resolve_value(raw, props, "3", spell_index)

    template = props["Description"]
    return INDENT + eval('f"' + template + '"')


def _resolve_value(raw, props, suffix, spell_index):
    """解析一个条件值：映射表 ValueN 以 spell 开头时换成带引号的技能名，否则原样保留数字。"""
    value = raw.get(f"ConditionValue{suffix}")
    if str(props[f"Value{suffix}"]).lower().startswith("spell"):
        return f"'{spell_index.display_name(value)}'"
    return value


def render_rotation(condition_map, steps, spell_index):
    """把一个专精方案的全部步骤渲染成文本（不含首行的专精显示名）。

    结构：``N: Spell: <技能名>`` + 该步的若干条缩进条件行；N 从 0 开始，
    顺序 = 传入的步骤顺序（= AssistedCombatStep 的 CSV 行序，不按 OrderIndex 排序）。
    """
    lines = []
    for step_index, step in enumerate(steps):
        spell_name = spell_index.display_name(step["SpellID"])
        lines.append(f"{step_index}: Spell: {spell_name}")
        for rule in step["rules"].values():
            lines.append(render_rule(condition_map, rule, spell_name, spell_index))
    return "\n".join(lines)
