"""技能名索引：命中、缺失占位、ID 标签与可选的 cd 后缀，以及"只保留所需 ID"的流式扫描行为。"""

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
    """19434 = 瞄准射击（猎人射击专精的充能条件使用该 ID）。"""
    index, _ = spell_index
    assert index.get_name(19434) == "瞄准射击"
    assert index.display_name(19434) == "瞄准射击"


def test_labelled_appends_decimal_id(spell_index):
    """标签格式固定为 <名称>[id:<spellID>]：原样十进制、不补零、名称与中括号之间无空格。

    瞄准射击的冷却两列都是 0，因此不加 cd 后缀。
    """
    index, _ = spell_index
    assert index.labelled(19434) == "瞄准射击[id:19434]"


def test_labelled_appends_cooldown_over_one_second(spell_index):
    """冷却大于 1 秒时追加 ,cd:<整数秒>：死神印记 45000ms → 45。"""
    index, _ = spell_index
    assert index.labelled(439843) == "死神印记[id:439843,cd:45]"


def test_labelled_omits_cooldown_at_or_below_threshold(spell_index):
    """阈值是"严格大于 1000ms"：正好 1000ms（正义盾击）与表里没有的 ID（减速药膏）都不加 cd。"""
    index, _ = spell_index
    assert index.labelled(53600) == "正义盾击[id:53600]"
    assert index.labelled(3408) == "减速药膏[id:3408]"


def test_missing_ids_render_placeholder(spell_index):
    """查不到名称的 ID：裸名是 Unknown Spell，带标签时 ID 由标签统一附带。"""
    index, _ = spell_index
    for spell_id in MISSING_IDS:
        assert index.get_name(spell_id) is None
        assert index.display_name(spell_id) == "Unknown Spell"
        assert index.labelled(spell_id) == f"Unknown Spell[id:{spell_id}]"


def test_index_only_keeps_required_ids(spell_index):
    """索引只保留所需 ID，而不是整表缓存（ID=1 在 SpellName 表里存在但本次不需要）。"""
    index, required_ids = spell_index
    assert 1 not in required_ids
    assert index.get_name(1) is None
