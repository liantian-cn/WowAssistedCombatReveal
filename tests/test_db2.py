"""DB2 嵌套结构与专精查找的规模测试（数据快照 12.1.0.69814）。"""

import main
from app import db2

EXPECTED_CLASSES = 15  # 13 个玩家职业 + Adventurer + Traveler（后两个没有辅助方案）
EXPECTED_SPEC_ROWS = 60  # ChrSpecialization 表的行数
EXPECTED_ATTACHED_SPECS = 54  # 能挂到职业下的专精：6 个宠物天赋专精 ClassID=0，旧版同样不挂载
EXPECTED_PLANS = 40
EXPECTED_STEPS = 693
EXPECTED_RULES = 3116


def all_specs(classes):
    """展开嵌套结构里的全部专精。"""
    return [spec for class_data in classes.values() for spec in class_data["specs"].values()]


def test_spec_table_scale(classes, csv_dir):
    """ChrSpecialization 60 行，其中 54 行挂到职业下（6 个宠物天赋专精的 ClassID=0 无对应职业）。"""
    spec_rows = db2.read_table(csv_dir, "ChrSpecialization", main.VERSION)
    assert len(spec_rows) == EXPECTED_SPEC_ROWS
    assert len(all_specs(classes)) == EXPECTED_ATTACHED_SPECS
    assert {"Ferocity", "Cunning", "Tenacity"} & {spec["Name"] for spec in all_specs(classes)} == set()


def test_plan_scale(classes):
    """4 张表规模：15 职业 / 40 方案 / 693 步骤 / 3116 规则；规则数等于 CSV 行数，无 OrderIndex 覆盖。"""
    assert len(classes) == EXPECTED_CLASSES
    steps = list(db2.iter_plan_steps(classes))
    # 规则总数与 CSV 行数一致，说明没有 OrderIndex 键冲突导致的静默覆盖
    rules = [rule for step in steps for rule in step["rules"].values()]
    assert len(steps) == EXPECTED_STEPS
    assert len(rules) == EXPECTED_RULES
    assert len([spec for spec in all_specs(classes) if spec.get("assist_plan")]) == EXPECTED_PLANS


def test_specs_with_plan_cover_13_classes(classes):
    """有方案的专精恰好 40 个、覆盖 13 个职业（Adventurer / Traveler 不在其中）。"""
    class_names = [class_name for class_name, _spec in db2.iter_specs_with_plan(classes)]
    assert len(class_names) == EXPECTED_PLANS
    assert len(set(class_names)) == 13
    assert "Adventurer" not in set(class_names)
    assert "Traveler" not in set(class_names)


def test_find_spec_matches_only_within_class(classes):
    """同名专精（Frost / Holy / Protection / Restoration）必须限定在本职业内匹配。"""
    assert db2.find_spec(classes, "Hunter", "Beast Mastery") is not None
    assert db2.find_spec(classes, "Hunter", "Frost") is None
    assert db2.find_spec(classes, "Mage", "Frost") is not None
    assert db2.find_spec(classes, "Priest", "Holy")["ID"] != db2.find_spec(classes, "Paladin", "Holy")["ID"]
    assert db2.find_spec(classes, "Nope", "Arms") is None


def test_find_spec_accepts_camelcase_and_display_names(classes):
    """专精查找兼容旧版 CLI 的 CamelCase 写法与 CSV 显示名两种输入。"""
    by_display = db2.find_spec(classes, "Hunter", "Beast Mastery")
    by_camel = db2.find_spec(classes, "Hunter", "BeastMastery")
    assert by_display is not None
    assert by_camel is by_display
    assert by_camel["Name"] == "Beast Mastery"
    # 连写职业名（DeathKnight / DemonHunter）同样命中（专精名保持原样也能查）
    assert db2.find_spec(classes, "DeathKnight", "Blood") is db2.find_spec(classes, "Death Knight", "Blood")
    assert db2.find_spec(classes, "DemonHunter", "Devourer") is not None
    # 不会跨职业串名（Hunter 没有 Frost），单名专精两种写法都命中
    assert db2.find_spec(classes, "Hunter", "Frost") is None
    assert db2.find_spec(classes, "Rogue", "Assassination") is not None
