"""条件渲染：加载 ConditionTypeMap.csv，把规则渲染成 4 空格缩进、末尾带类型注释的可读文本行。

条件行形态：``<4 空格缩进><模板渲染结果><8 空格>-- <Enum>``。注释里的 ``<Enum>`` 取自
``ConditionTypeMap.csv`` 的 ``Enum`` 列（如 ``ASSISTED_COMBAT_RULE_TYPE_AFFORD_COST``），
把中文条件描述与该规则在 DB2 ``AssistedCombatRule.ConditionType`` 里的原始枚举名直接对照。
所有条件行（含 ``ASSISTED_COMBAT_RULE_TYPE_AUTOMATION_ONLY`` 说明行）统一追加注释，
步骤标题行与首行专精名不加；间隔固定 8 空格，按条件文本长度自然错开、不做列对齐
（条件文本含中文与变长技能名，对齐需按显示宽度计算）。

沿用旧版实现的关键点：

1. 模板用 ``eval('f"…"')`` 渲染，模板里可用的变量是 ``spell`` / ``arg1`` / ``arg2`` / ``arg3``。
   限制只存在于**模板侧**（``Description`` 列）：不能含双引号（会截断 f-string 字面量）、
   反斜杠（会被当转义），``{`` ``}`` 只能是设计好的占位符；技能名与条件值是作为变量值
   插入的，含撇号等任意字符都安全（如 ``'The Emperor's Capacitor'``）。
2. ``ValueN`` 列以 "spell"（不分大小写）开头时，``ConditionValueN`` 先解析为技能名再加单引号；
   技能名找不到时使用 ``Unknown Spell[id:<spellID>]`` 占位（旧版会在这里崩）。

本期新增：

3. 所有由 spellID 解析出的名称都带 ``[id:<spellID>]`` 后缀（见
   :meth:`app.spells.SpellIndex.labelled`），把输出行与 DB2 的 ID 直接对应起来。
4. 所有条件行末尾追加 ``<8 空格>-- <Enum>`` 类型注释（``Enum`` 列），供与 DB2 条件类型对照。

与旧版的差异（第一期确认的修正之一）：映射表未覆盖的条件类型不再抛 ``IndexError``，
而是抛出带 ConditionType 与规则 ID 的 ``ValueError``，便于定位缺失的映射行。
"""

import pandas as pd

# 与 db2 模块一致的 CSV 读取参数
CSV_READ_ARGS = {"quoting": 0, "engine": "python", "quotechar": '"'}

# 条件行固定缩进，旧版为 4 空格
INDENT = "    "

# 条件行末尾类型注释前的固定间隔：8 空格（不做列对齐，条件文本长度不定）
COMMENT_GAP = "        "


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


def render_rule(condition_map, rule, spell_id, spell_index):
    """渲染一条规则为一行文本（含 4 空格缩进与末尾的类型注释）。

    ``rule`` 是嵌套结构里的规则条目（用 ``raw`` 取条件值、用 ``ID`` 报错）；
    ``spell_id`` 是当前步骤的技能 ID，``spell_index`` 用于把它和 Spell 型参数
    一起解析成带 ID 标签的技能名。步骤标题与条件行都从同一个 ID 取名称，
    因此两种行里的名称与标签必然一致。

    行尾统一追加 ``COMMENT_GAP + "-- " + Enum``：枚举名取自映射表 ``Enum`` 列，
    覆盖全部条件行（含 automation-only 说明行），便于与 DB2 的 ConditionType 对照。
    """
    raw = rule["raw"]
    condition_type = raw.get("ConditionType")
    props = condition_props(condition_map, condition_type, rule.get("ID"))

    # 模板变量：spell 是当前步骤技能名；arg1..arg3 是条件值（Spell 型列已解析为带引号的技能名）
    spell = f"'{spell_index.labelled(spell_id)}'"
    arg1 = _resolve_value(raw, props, "1", spell_index)
    arg2 = _resolve_value(raw, props, "2", spell_index)
    arg3 = _resolve_value(raw, props, "3", spell_index)

    template = props["Description"]
    line = INDENT + eval('f"' + template + '"')
    return line + COMMENT_GAP + "-- " + props["Enum"]


def _resolve_value(raw, props, suffix, spell_index):
    """解析一个条件值：映射表 ValueN 以 spell 开头时换成带引号且带 ID 标签的技能名，否则原样保留数字。"""
    value = raw.get(f"ConditionValue{suffix}")
    if str(props[f"Value{suffix}"]).lower().startswith("spell"):
        return f"'{spell_index.labelled(value)}'"
    return value


def render_rotation(condition_map, steps, spell_index):
    """把一个专精方案的全部步骤渲染成文本（不含首行的专精显示名）。

    结构：``N: Spell: <技能名>[id:<spellID>]`` + 该步的若干条缩进条件行（末尾带类型注释）；
    N 从 0 开始，顺序 = 传入的步骤顺序（= AssistedCombatStep 的 CSV 行序，不按 OrderIndex 排序）。
    """
    lines = []
    for step_index, step in enumerate(steps):
        spell_id = step["SpellID"]
        lines.append(f"{step_index}: Spell: {spell_index.labelled(spell_id)}")
        for rule in step["rules"].values():
            lines.append(render_rule(condition_map, rule, spell_id, spell_index))
    return "\n".join(lines)
