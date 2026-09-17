"""技能名索引：用标准库 csv 单次流式扫描 SpellName 表，只保留本次需要的技能 ID。

旧版对每个技能 ID 联网抓取名称并缓存 JSON；新版完全离线，名称取自
``csv_table/SpellName.<版本>.csv``（列：ID,Name_lang；字段带引号，值里可能有逗号）。
SpellName 表约 11MB / 41 万行，因此只做一次顺序扫描，并且只把命中行放进内存，
不整体载入 DataFrame，也不整表缓存。

输出里的技能名必须可追溯回 spellID，因此统一走 :meth:`SpellIndex.labelled`：
命中时返回 ``<名称>[id:<spellID>]``，技能冷却大于 1 秒时再追加 ``,cd:<整数秒>``
（如 ``死神印记[id:439843,cd:45]``，冷却来自 :mod:`app.cooldowns`）；
表中查不到名称的 ID（本期数据有 3 个：194310 / 389387 / 470058）返回
``Unknown Spell[id:<spellID>]`` 占位，不报错也不中断渲染。
"""

import csv
import logging

_logger = logging.getLogger(__name__)

# 表中没有该 ID 时的占位文本（不中断渲染；ID 由 :meth:`SpellIndex.labelled` 统一附带）
UNKNOWN_SPELL_NAME = "Unknown Spell"


class SpellIndex:
    """技能 ID → 名称的只读映射，只保存本次需要的 ID；可选携带冷却索引。"""

    def __init__(self, names=None, cooldowns=None):
        self._names = dict(names or {})
        # None 表示不显示任何 cd（只查名字的场景，如单元测试）；否则用 CooldownIndex 取秒数
        self._cooldowns = cooldowns

    def get_name(self, spell_id):
        """返回技能名；未收录（表里没有该 ID）时返回 None。"""
        return self._names.get(int(spell_id))

    def display_name(self, spell_id):
        """返回不带 ID 标签的显示名；未收录时返回 ``Unknown Spell`` 占位文本。

        名称本身不带冷却信息，cd 只加在 :meth:`labelled` 生成的标签里。
        """
        name = self.get_name(spell_id)
        if name is None:
            return UNKNOWN_SPELL_NAME
        return name

    def labelled(self, spell_id):
        """返回"名称 + ID 标签"：``<名称>[id:<spellID>]``；冷却 > 1 秒时追加 ``,cd:<整数秒>``。

        渲染输出里的技能名一律经过这里，文本才能直接对照 DB2 中的 spellID；
        未收录的 ID 输出 ``Unknown Spell[id:<spellID>]``。
        """
        spell_id = int(spell_id)
        suffix = ""
        if self._cooldowns is not None:
            seconds = self._cooldowns.seconds(spell_id)
            if seconds is not None:
                suffix = f",cd:{seconds}"
        return f"{self.display_name(spell_id)}[id:{spell_id}{suffix}]"

    def __len__(self):
        return len(self._names)


def _spell_value_columns(condition_map):
    """映射表中"值语义以 spell 开头"的条件类型 → 需要解析成技能名的 ConditionValueN 列名。

    每个 ValueN 列独立判断（与渲染时的逐列判断一致），同一类型可能有多列是技能 ID。
    """
    columns = {}
    for props in condition_map.itertuples():
        for suffix in ("1", "2", "3"):
            if str(getattr(props, f"Value{suffix}")).lower().startswith("spell"):
                columns.setdefault(int(props.Type), []).append(f"ConditionValue{suffix}")
    return columns


def collect_required_spell_ids(steps, condition_map):
    """收集本次渲染要用到的技能 ID：步骤技能 + Spell 型规则参数，0 除外。

    0 是 DB2 里"该字段未使用"的填充值，不能拿去查名字。
    """
    columns = _spell_value_columns(condition_map)
    required = set()
    for step in steps:
        required.add(int(step["SpellID"]))
        for rule in step["rules"].values():
            raw = rule["raw"]
            for column in columns.get(int(raw["ConditionType"]), ()):
                required.add(int(raw[column]))
    required.discard(0)
    return required


def read_spell_index(path, required_ids, cooldowns=None):
    """单次流式扫描 SpellName 表，返回只包含 required_ids 的 :class:`SpellIndex`。

    逐行读取，命中才解析名称；所需 ID 全部找到后立即停止读取。
    ``cooldowns`` 是可选冷却索引，透传给 :class:`SpellIndex` 供 cd 标签使用。
    """
    missing = {int(spell_id) for spell_id in required_ids}
    names = {}
    with open(path, "r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        next(reader)  # 跳过表头 ID,Name_lang
        for row in reader:
            if len(row) < 2:
                continue
            try:
                spell_id = int(row[0])
            except ValueError:
                continue
            if spell_id in missing:
                names[spell_id] = row[1]
                missing.discard(spell_id)
                if not missing:
                    break
    if missing:
        _logger.warning(f"SpellName 表中缺少 {len(missing)} 个技能 ID：{sorted(missing)}")
    return SpellIndex(names, cooldowns)
