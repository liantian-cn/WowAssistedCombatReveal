"""技能名索引：命中、缺失占位，以及"只保留所需 ID"的流式扫描行为。"""

MISSING_IDS = (194310, 389387, 470058)  # 12.1 规则引用了但 SpellName 表里没有的 ID


def test_required_ids_and_hits(spell_index):
    """需求 ID 551 个，命中 548 个，缺失 3 个。"""
    index, required_ids = spell_index
    assert len(required_ids) == 551
    assert len(index) == 548
    assert set(MISSING_IDS) <= required_ids
    for spell_id in MISSING_IDS:
        assert index.get_name(spell_id) is None


def test_known_spell_name(spell_index):
    """19434 = Aimed Shot（猎人射击专精的充能条件使用该 ID）。"""
    index, _ = spell_index
    assert index.get_name(19434) == "Aimed Shot"


def test_missing_ids_render_placeholder(spell_index):
    """查不到名称的 ID 返回 None，显示名用 Unknown Spell (ID) 占位。"""
    index, _ = spell_index
    for spell_id in MISSING_IDS:
        assert index.get_name(spell_id) is None
        assert index.display_name(spell_id) == f"Unknown Spell ({spell_id})"


def test_index_only_keeps_required_ids(spell_index):
    """索引只保留所需 ID，而不是整表缓存（ID=1 在 SpellName 表里存在但本次不需要）。"""
    index, required_ids = spell_index
    assert 1 not in required_ids
    assert index.get_name(1) is None
