"""条件渲染：模板占位符、充能层数、automation-only 说明行、ID 标签、类型注释、未知类型报错。"""

import re

import pytest

from app import render

# 条件行末尾注释的固定间隔：8 空格（这里写死字面量，避免与实现常量一起被改掉而失去约束）
COMMENT_GAP = "        "
# 校验用正则：注释前必须**恰好** 8 个空格——`[^ ]` 排除"第 9 个空格"的情况
# （只写 ` {8}` 时 9 个空格也能匹配成功），行尾锚定，枚举名允许大写字母/数字/下划线
COMMENT_RE = re.compile(r"[^ ] {8}-- ASSISTED_COMBAT_RULE_TYPE_[A-Z0-9_]+$")
AUTOMATION_ONLY_TEXT = "仅自动化施放（不属于游戏的辅助战斗循环）"


def condition_line(text, enum):
    """按约定拼出一整条条件行：4 空格缩进 + 渲染文本 + 8 空格 + "-- " + 枚举名。"""
    return f"    {text}{COMMENT_GAP}-- {enum}"


def map_enum(condition_map, condition_type):
    """映射表 Enum 列里该条件类型的原始枚举名（期望值一律由映射表算出，不写死）。"""
    return render.condition_props(condition_map, condition_type, 0)["Enum"]


def find_rule(plan_steps, condition_type=None, rule_id=None):
    """在渲染数据里按条件类型或规则 ID 找规则，找不到直接失败。"""
    for step in plan_steps:
        for rule in step["rules"].values():
            if condition_type is not None and int(rule["raw"]["ConditionType"]) != condition_type:
                continue
            if rule_id is not None and int(rule["raw"]["ID"]) != rule_id:
                continue
            return step, rule
    raise AssertionError(f"数据里没有找到 ConditionType={condition_type} / rule_id={rule_id} 的规则")


def test_charge_rule_renders_number(condition_map, plan_steps, spell_index):
    """类型 63 的 Value1 是充能层数：必须输出数字，不能出现 'Spells' charges 这种技能名误判。"""
    index, _ = spell_index
    step, rule = find_rule(plan_steps, condition_type=63)
    line = render.render_rule(condition_map, rule, step["SpellID"], index)
    assert line == condition_line(
        f"若技能 '{index.labelled(step['SpellID'])}' 的充能层数大于等于 2",
        map_enum(condition_map, 63),
    )
    assert "'Spells'" not in line
    assert "Charge Count" not in line
    # 层数是数值参数，不带标签；技能名照常带
    assert "[id:2]" not in line


def test_numeric_arguments_have_no_id_label(condition_map, plan_steps, spell_index):
    """数值型参数（目标数 / 距离）保持原样：整行不出现 [id: （注释只含枚举名）。"""
    index, _ = spell_index
    step, rule = find_rule(plan_steps, condition_type=12)
    line = render.render_rule(condition_map, rule, step["SpellID"], index)
    assert re.fullmatch(
        r"    若玩家周围 \d+ 码内的目标数量大于 \d+ 个" + COMMENT_GAP + "-- " + map_enum(condition_map, 12),
        line,
    )
    assert "[id:" not in line


def test_automation_only_rule_line(condition_map, plan_steps, spell_index):
    """类型 70 渲染为映射表里的说明行（模板无占位符，因此不带 ID 标签），同样带类型注释。"""
    index, _ = spell_index
    step, rule = find_rule(plan_steps, condition_type=70)
    line = render.render_rule(condition_map, rule, step["SpellID"], index)
    assert line == condition_line(AUTOMATION_ONLY_TEXT, map_enum(condition_map, 70))
    assert line.endswith("        -- ASSISTED_COMBAT_RULE_TYPE_AUTOMATION_ONLY")
    assert "[id:" not in line


def test_missing_spell_argument_uses_placeholder(condition_map, plan_steps, spell_index):
    """规则 4828（Unholy，类型 10）引用了 SpellName 表里没有的 194310，输出带 ID 的占位文本。"""
    index, _ = spell_index
    step, rule = find_rule(plan_steps, rule_id=4828)
    line = render.render_rule(condition_map, rule, step["SpellID"], index)
    assert line == condition_line("若目标拥有增益/减益 'Unknown Spell[id:194310]'", map_enum(condition_map, 10))
    assert "Unknown Spell (" not in line


def test_spell_argument_resolved_to_name(condition_map, plan_steps, spell_index):
    """Spell 型参数解析为带单引号、带 ID 标签的技能名（规则 32，类型 15 的参数 703 = 锁喉）。

    锁喉冷却 6000ms，因此标签里还有 cd:6。
    """
    index, _ = spell_index
    step, rule = find_rule(plan_steps, rule_id=32)
    line = render.render_rule(condition_map, rule, step["SpellID"], index)
    assert line == condition_line("若目标没有增益/减益 '锁喉[id:703,cd:6]'", map_enum(condition_map, 15))


def test_unknown_condition_type_raises(condition_map, spell_index):
    """映射表缺行时抛出带 ConditionType 与规则 ID 的 ValueError（旧版是 IndexError）。"""
    index, _ = spell_index
    rule = {
        "ID": 999999,
        "OrderIndex": 0,
        "raw": {"ConditionType": 999, "ConditionValue1": 0, "ConditionValue2": 0, "ConditionValue3": 0},
    }
    with pytest.raises(ValueError) as excinfo:
        render.render_rule(condition_map, rule, 12345, index)
    assert "ConditionType=999" in str(excinfo.value)
    assert "999999" in str(excinfo.value)


def test_rotation_numbering_starts_at_zero(condition_map, plan_steps, spell_index):
    """步骤编号从 0 连续，标题行带 ID 标签（冷却 > 1 秒时还有 cd）且不带注释；
    条件行 4 空格缩进且末尾带类型注释。
    """
    index, _ = spell_index
    body = render.render_rotation(condition_map, plan_steps[:3], index)
    lines = body.splitlines()
    numbers = [int(line.split(":", 1)[0]) for line in lines if ": Spell: " in line]
    assert numbers == [0, 1, 2]
    for line in lines:
        if ": Spell: " in line:
            assert re.match(r"^\d+: Spell: .+\[id:\d+(,cd:\d+)?\]$", line), line
            assert "-- " not in line
        else:
            assert line.startswith("    ") and len(line) > 4
            assert COMMENT_RE.search(line), line


def test_title_and_condition_share_same_label(condition_map, spell_index):
    """同一步骤的标题行与 {spell} 条件行取自同一个 ID：名称与标签完全一致。

    标题行不加引号也不加注释、条件行带单引号且末尾带类型注释（引号与注释规则）；
    瞄准射击无冷却，因此都不带 cd。
    """
    index, _ = spell_index
    step = {
        "SpellID": 19434,
        "rules": {
            0: {
                "ID": 1,
                "OrderIndex": 0,
                "raw": {"ConditionType": 0, "ConditionValue1": 0, "ConditionValue2": 0, "ConditionValue3": 0},
            },
        },
    }
    body = render.render_rotation(condition_map, [step], index)
    assert body == (
        "0: Spell: 瞄准射击[id:19434]\n"
        + condition_line("若已点出天赋 '瞄准射击[id:19434]'", map_enum(condition_map, 0))
    )
