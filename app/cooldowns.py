"""技能冷却索引：用标准库 csv 单次流式扫描 SpellCooldowns 表，只保留本次需要的技能 ID。

数据来源为 ``csv_table/SpellCooldowns.<版本>.csv``（表头实测：
``ID,DifficultyID,CategoryRecoveryTime,RecoveryTime,StartRecoveryTime,AuraSpellID,SpellID``）：

- 冷却时长有两列（毫秒）：第 3 列 ``CategoryRecoveryTime``、第 4 列 ``RecoveryTime``。
  两列都是真实冷却，只取第 4 列会漏掉 17 个"冷却只写在第 3 列"的技能
  （眼棱 198013、恶魔变形 191427、复仇之怒 31884 等），因此取两列的较大值；
- 第 5 列 ``StartRecoveryTime`` 是 GCD 类字段，与技能冷却无关，不参与计算；
- 同一个 SpellID 可能在表里有多行（DifficultyID 等差异），取所有行的最大值；
- 真正需要的是最后一列 ``SpellID``，第 1 列 ``ID`` / 第 6 列 ``AuraSpellID`` 与本项目无关。

表约 36k 行 / 1MB，只做一次顺序扫描，只把命中行放进内存。冻结口径要求每个 SpellID 的冷却
取该 ID **全部行**的最大值，因此这里不能像 SpellName 那样"全部命中即停"，整张表都会被读完，
否则同一 SpellID 靠后的更大值会被漏掉。表中查不到冷却的技能不参与 cd 标签，也不算错误。
"""

import csv
import logging

_logger = logging.getLogger(__name__)

# 冷却表列位置（0 基）与最少列数；换表结构时只需改这里
_COLUMN_CATEGORY_RECOVERY = 2
_COLUMN_RECOVERY = 3
_COLUMN_SPELL_ID = 6
_COLUMN_COUNT = 7

# cd 标签的显示阈值：原始毫秒严格大于该值才显示（正好 1000ms 不显示）
_COOLDOWN_THRESHOLD_MS = 1000


class CooldownIndex:
    """技能 ID → 冷却毫秒的只读映射，只保存本次需要的 ID。"""

    def __init__(self, milliseconds=None):
        self._milliseconds = dict(milliseconds or {})

    def milliseconds(self, spell_id):
        """返回技能冷却毫秒值（同一 ID 多行时取最大值）；表中没有该 ID 时返回 None。"""
        return self._milliseconds.get(int(spell_id))

    def seconds(self, spell_id):
        """返回显示用整数秒；冷却不存在或不超过 1 秒时返回 None。

        四舍五入按中文语义"0.5 向上"：``(ms + 500) // 1000``（1500→2、4500→5）。
        不用内置 ``round()``：银行家舍入会把 4500 变成 4。
        """
        milliseconds = self.milliseconds(spell_id)
        if milliseconds is None or milliseconds <= _COOLDOWN_THRESHOLD_MS:
            return None
        return (milliseconds + 500) // 1000

    def __len__(self):
        return len(self._milliseconds)


def read_cooldown_index(path, required_ids):
    """单次流式扫描 SpellCooldowns 表（整表读完），返回只包含 required_ids 的 :class:`CooldownIndex`。

    逐行读取。冷却两列都要能解析成整数才参与取大，脏行跳过（不中断）。
    为取到每个需求 ID 所有行的最大值，这里不做提前停止；只有需求 ID 的行会写进内存。
    """
    required = {int(spell_id) for spell_id in required_ids}
    milliseconds = {}
    with open(path, "r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        next(reader)  # 跳过表头
        for row in reader:
            if len(row) < _COLUMN_COUNT:
                continue
            try:
                spell_id = int(row[_COLUMN_SPELL_ID])
                category = int(row[_COLUMN_CATEGORY_RECOVERY])
                recovery = int(row[_COLUMN_RECOVERY])
            except ValueError:
                continue
            if spell_id in required:
                value = max(category, recovery)
                milliseconds[spell_id] = max(milliseconds.get(spell_id, 0), value)
    absent = required - milliseconds.keys()
    if absent:
        # 表里没有记录是常态（本期 551 个需求 ID 中 217 个如此），不算异常，用 info 记录数量
        _logger.info(f"{len(absent)} 个技能 ID 在 SpellCooldowns 表中没有记录，这些技能不加 cd 标签")
    return CooldownIndex(milliseconds)
