"""技能名索引：用标准库 csv 单次流式扫描 SpellName 表，只保留本次需要的技能 ID。

旧版对每个技能 ID 联网抓取名称并缓存 JSON；新版完全离线，名称取自
``csv_table/SpellName.<版本>.csv``（列：ID,Name_lang；字段带引号，值里可能有逗号）。
SpellName 表约 11MB / 41 万行，因此只做一次顺序扫描，并且只把命中行放进内存，
不整体载入 DataFrame，也不整表缓存。

表中查不到名称的 ID（本期数据有 3 个：194310 / 389387 / 470058）不报错，
由 :meth:`SpellIndex.display_name` 渲染成 ``Unknown Spell (ID)`` 占位。
"""

import csv
import logging

_logger = logging.getLogger(__name__)

# 表中没有该 ID 时的占位文本（不中断渲染）
UNKNOWN_SPELL_NAME = "Unknown Spell ({spell_id})"


class SpellIndex:
    """技能 ID → 名称的只读映射，只保存本次需要的 ID。"""

    def __init__(self, names=None):
        self._names = dict(names or {})

    def get_name(self, spell_id):
        """返回技能名；未收录（表里没有该 ID）时返回 None。"""
        return self._names.get(int(spell_id))

    def display_name(self, spell_id):
        """返回技能名；未收录时返回 ``Unknown Spell (ID)`` 占位文本。"""
        name = self.get_name(spell_id)
        if name is None:
            return UNKNOWN_SPELL_NAME.format(spell_id=int(spell_id))
        return name

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


def read_spell_index(path, required_ids):
    """单次流式扫描 SpellName 表，返回只包含 required_ids 的 :class:`SpellIndex`。

    逐行读取，命中才解析名称；所需 ID 全部找到后立即停止读取。
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
    return SpellIndex(names)
