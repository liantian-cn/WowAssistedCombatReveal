"""条件渲染：模板占位符、充能层数、automation-only 说明行、未知类型报错。"""

import pytest

from app import render

AUTOMATION_ONLY_LINE = "    automation only (not part of the game's Assisted Combat rotation)"


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
    line = render.render_rule(condition_map, rule, index.display_name(step["SpellID"]), index)
    assert line.startswith("    if player has more than 2 charges of spell '")
    assert "'Spells'" not in line
    assert "Charge Count" not in line


def test_automation_only_rule_line(condition_map, plan_steps, spell_index):
    """类型 70 渲染为映射表新增的说明行（模板无占位符）。"""
    index, _ = spell_index
    step, rule = find_rule(plan_steps, condition_type=70)
    line = render.render_rule(condition_map, rule, index.display_name(step["SpellID"]), index)
    assert line == AUTOMATION_ONLY_LINE


def test_missing_spell_argument_uses_placeholder(condition_map, plan_steps, spell_index):
    """规则 4828（Unholy，类型 10）引用了 SpellName 表里没有的 194310，输出占位文本。"""
    index, _ = spell_index
    step, rule = find_rule(plan_steps, rule_id=4828)
    line = render.render_rule(condition_map, rule, index.display_name(step["SpellID"]), index)
    assert line == "    if target has buff/debuff 'Unknown Spell (194310)'"


def test_spell_argument_resolved_to_name(condition_map, plan_steps, spell_index):
    """Spell 型参数解析为带单引号的技能名（规则 32，类型 15 的参数 703 = Garrote）。"""
    index, _ = spell_index
    step, rule = find_rule(plan_steps, rule_id=32)
    line = render.render_rule(condition_map, rule, index.display_name(step["SpellID"]), index)
    assert line == "    if target does not have buff/debuff 'Garrote'"


def test_unknown_condition_type_raises(condition_map, spell_index):
    """映射表缺行时抛出带 ConditionType 与规则 ID 的 ValueError（旧版是 IndexError）。"""
    index, _ = spell_index
    rule = {
        "ID": 999999,
        "OrderIndex": 0,
        "raw": {"ConditionType": 999, "ConditionValue1": 0, "ConditionValue2": 0, "ConditionValue3": 0},
    }
    with pytest.raises(ValueError) as excinfo:
        render.render_rule(condition_map, rule, "Test Spell", index)
    assert "ConditionType=999" in str(excinfo.value)
    assert "999999" in str(excinfo.value)


def test_rotation_numbering_starts_at_zero(condition_map, plan_steps, spell_index):
    """步骤编号从 0 连续，条件行 4 空格缩进。"""
    index, _ = spell_index
    body = render.render_rotation(condition_map, plan_steps[:3], index)
    lines = body.splitlines()
    numbers = [int(line.split(":", 1)[0]) for line in lines if ": Spell: " in line]
    assert numbers == [0, 1, 2]
    for line in lines:
        if ": Spell: " not in line:
            assert line.startswith("    ") and len(line) > 4
