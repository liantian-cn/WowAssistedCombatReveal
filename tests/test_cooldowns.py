"""技能冷却索引：两列取大、缺失/阈值边界、半进到整数秒，以及"只保留所需 ID"。

另有一条独立重算测试：直接读原始 SpellCooldowns CSV 算出期望标签，与
``SpellIndex.labelled()`` 逐 ID 比对，任何数值 / 阈值 / 四舍五入错误都会失败。
"""

import csv
from pathlib import Path

import main
from app import cooldowns, db2

# 抽查 ID（12.1.0.69814 实测）：
REAPERS_MARK = 439843          # 死神印记：CategoryRecoveryTime=45000 / RecoveryTime=0
EYE_BEAM = 198013              # 眼棱：冷却只写在第 3 列 CategoryRecoveryTime=30000
DARK_TRANSFORMATION = 1233448  # 黑暗突变：CategoryRecoveryTime=1500 / RecoveryTime=45000，必须取大
AIMED_SHOT = 19434             # 冷却两列都是 0
MULTI_SHOT = 257620            # 冷却两列都是 0
DEADLY_POISON = 3408           # 冷却表里没有该 ID
SHIELD_OF_THE_RIGHTEOUS = 53600  # 正好 1000ms：阈值是"严格大于"，不加 cd
CHI_BURST = 461404             # 100ms：低于阈值
IMMOLATION_AURA = 258920       # 1500ms → 2 秒（半进）
BLOODTHIRST = 23881            # 4500ms → 5 秒（半进；内置 round() 会得到 4）


def _max_milliseconds_from_csv(csv_dir):
    """直接读原始 CSV 重算"两列取大、同一 SpellID 多行再取大"的毫秒值（不经过 app.cooldowns）。"""
    table = Path(csv_dir) / db2.table_filename("SpellCooldowns", main.VERSION)
    result = {}
    with open(table, "r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        next(reader)
        for row in reader:
            if len(row) < 7:
                continue
            try:
                spell_id = int(row[6])
                value = max(int(row[2]), int(row[3]))
            except ValueError:
                continue
            result[spell_id] = max(result.get(spell_id, 0), value)
    return result


def test_max_of_both_cooldown_columns(cooldown_index):
    """两列取大：第 3 列 CategoryRecoveryTime 与第 4 列 RecoveryTime 谁大用谁。"""
    assert cooldown_index.milliseconds(REAPERS_MARK) == 45000
    assert cooldown_index.milliseconds(EYE_BEAM) == 30000
    assert cooldown_index.milliseconds(DARK_TRANSFORMATION) == 45000


def test_missing_and_zero_cooldowns(cooldown_index):
    """表里没有的 ID 返回 None；两列为 0 的技能返回 0（不是 None）。"""
    assert cooldown_index.milliseconds(DEADLY_POISON) is None
    assert cooldown_index.milliseconds(AIMED_SHOT) == 0
    assert cooldown_index.milliseconds(MULTI_SHOT) == 0


def test_threshold_is_strictly_greater_than_one_second(cooldown_index):
    """阈值按原始毫秒严格大于 1000：正好 1000ms 与 100ms 都不显示，45000ms 显示 45。"""
    assert cooldown_index.seconds(SHIELD_OF_THE_RIGHTEOUS) is None
    assert cooldown_index.seconds(CHI_BURST) is None
    assert cooldown_index.seconds(REAPERS_MARK) == 45


def test_seconds_round_half_up(cooldown_index):
    """半进到整数秒：1500→2、4500→5（Python 内置 round() 会把 4500 变成 4）。"""
    assert cooldown_index.seconds(IMMOLATION_AURA) == 2
    assert cooldown_index.seconds(BLOODTHIRST) == 5


def test_index_only_keeps_required_ids(cooldown_index, required_spell_ids):
    """只保留所需 ID：17 是冷却表第一行数据的 SpellID，但本次不需要，因此查不到值。"""
    assert 17 not in required_spell_ids
    assert cooldown_index.milliseconds(17) is None
    # 551 个需求 ID 里命中冷却表 334 个（其余 217 个表里没有，渲染时不加 cd）
    assert len(cooldown_index) == 334


def test_multi_row_same_spell_id_takes_max(tmp_path):
    """同一 SpellID 多行时取最大值；大值出现在"需求 ID 全部出现过"之后也必须取到。

    旧实现"所需 ID 全部命中即停"会在第 2 行后停止，漏掉第 3 行里 100 的更大冷却；
    冻结口径要求取该 ID 全部行的最大值，因此必须整表读完（合成小表，不依赖真实数据）。
    """
    table = tmp_path / db2.table_filename("SpellCooldowns", "0")
    table.write_text(
        "ID,DifficultyID,CategoryRecoveryTime,RecoveryTime,StartRecoveryTime,AuraSpellID,SpellID\n"
        "1,0,0,0,1500,0,100\n"      # 100 先以小值出现
        "2,0,0,0,1500,0,200\n"      # 200 出现后，所有需求 ID 都已出现过（旧实现到此就会停止）
        "3,0,5000,0,1500,0,100\n",  # 100 的更大值在后面，必须整表读完才能取到
        encoding="utf-8",
    )
    index = cooldowns.read_cooldown_index(table, {100, 200})
    assert index.milliseconds(100) == 5000
    assert index.milliseconds(200) == 0


def test_labels_match_cooldown_csv_recomputed_independently(spell_index, csv_dir):
    """独立重算 CSV：每个需求 ID 的标签必须等于"两列取大 + 半进秒"的结果。

    期望值不经过 app.cooldowns，任何冷却取值、阈值或四舍五入错误都会在这里失败。
    """
    index, required_ids = spell_index
    expected_ms = _max_milliseconds_from_csv(csv_dir)
    cooled = 0
    for spell_id in required_ids:
        milliseconds = expected_ms.get(spell_id)
        suffix = ""
        if milliseconds is not None and milliseconds > 1000:
            suffix = f",cd:{(milliseconds + 500) // 1000}"
            cooled += 1
        assert index.labelled(spell_id) == f"{index.display_name(spell_id)}[id:{spell_id}{suffix}]"
    # 与 Q1 调查口径一致：551 个需求 ID 里 141 个带 cd
    assert cooled == 141
