"""输出层：命名规则与整库生成结果（40 个文件 / 13 个职业目录 / 已知修正点计数）。"""

import re
from pathlib import Path

import main
from app import output, render

AUTOMATION_ONLY_LINE = "    仅自动化施放（不属于游戏的辅助战斗循环）"
UNKNOWN_SPELL_IDS = (194310, 389387, 470058)


def outputs(generated):
    """返回 ``(输出目录, 全部输出文件列表)``。"""
    output_dir, _count = generated
    return output_dir, sorted(output_dir.rglob("*.txt"))


def test_naming_rules():
    """命名规则：小写 + 去空格，与旧版 run_all.ps1 的产物一致。"""
    assert output.class_directory_name("Death Knight") == "deathknight"
    assert output.class_directory_name("Demon Hunter") == "demonhunter"
    assert output.class_directory_name("Hunter") == "hunter"
    assert output.spec_file_name("Beast Mastery") == "beastmastery.txt"
    assert output.spec_file_name("Arms") == "arms.txt"


def test_generate_all_specs(generated):
    """整库生成 40 个文件、13 个职业目录，含新增的 Demon Hunter / Devourer。"""
    output_dir, count = generated
    _output_dir, files = outputs(generated)
    assert count == 40
    assert len(files) == 40
    assert len([path for path in output_dir.iterdir() if path.is_dir()]) == 13
    assert (output_dir / "demonhunter" / "devourer.txt").exists()
    assert (output_dir / "warrior" / "arms.txt").exists()
    assert (output_dir / "hunter" / "beastmastery.txt").exists()


def test_output_file_structure(generated):
    """每个文件：首行 = 专精显示名（与文件名对应）；步骤编号从 0 连续且标题带 ID；条件行 4 空格缩进。"""
    _output_dir, files = outputs(generated)
    for path in files:
        lines = path.read_text(encoding="utf-8").splitlines()
        assert lines, f"{path} 是空文件"
        assert lines[0].lower().replace(" ", "") == path.stem, f"{path} 首行与文件名不一致"
        numbers = []
        for line in lines[1:]:
            if ": Spell: " in line:
                assert re.match(r"^\d+: Spell: .+\[id:\d+(,cd:\d+)?\]$", line), f"{path}: 步骤行格式错误 {line!r}"
                numbers.append(int(line.split(":", 1)[0]))
            else:
                assert line.startswith("    ") and len(line) > 4, f"{path}: 条件行格式错误 {line!r}"
        assert numbers == list(range(len(numbers))), f"{path}: 步骤编号不连续 {numbers}"


def test_all_resolved_names_carry_id_labels(generated, plan_steps, condition_map, spell_index):
    """每一处由 spellID 解析出的名称都恰好带一个 [id:<spellID>] 标签。

    期望次数直接由原始数据算得：每个步骤标题 1 个 + 模板里每个引用技能名的占位符 1 个
    （``{spell}`` 与 ``ValueN`` 以 spell 开头且被模板引用的 ``{argN}``）。多一个或少一个都会失败。
    """
    _index, required_ids = spell_index
    expected = 0
    for step in plan_steps:
        expected += 1  # 步骤标题行
        for rule in step["rules"].values():
            props = render.condition_props(condition_map, rule["raw"]["ConditionType"], rule["ID"])
            description = str(props["Description"])
            expected += description.count("{spell}")
            for suffix in ("1", "2", "3"):
                if str(props[f"Value{suffix}"]).lower().startswith("spell"):
                    expected += description.count(f"{{arg{suffix}}}")

    _output_dir, files = outputs(generated)
    text = "\n".join(path.read_text(encoding="utf-8") for path in files)
    assert text.count("[id:") == expected
    # 标签里的 ID 必须都来自本次需求集合（不可能是凭空写死的数字）；cd 后缀可有可无
    assert {int(match) for match in re.findall(r"\[id:(\d+)(?:,cd:\d+)?\]", text)} <= required_ids
    # 没有任何一处仍使用旧占位写法
    assert "Unknown Spell (" not in text
    assert text.count("Unknown Spell") == 3


def test_charge_lines_use_numbers(generated):
    """类型 63 共 10 条，全部输出数字层数，不再出现 'Spells' charges 或 'Charge Count' 当技能名。"""
    _output_dir, files = outputs(generated)
    text = "\n".join(path.read_text(encoding="utf-8") for path in files)
    assert "'Spells' charges" not in text
    assert "'Charge Count'" not in text
    assert len(re.findall(r"的充能层数超过 \d+", text)) == 10
    # 层数不带标签，紧跟其后的技能名带标签（冷却 > 1 秒时还有 cd）
    assert len(re.findall(r"若技能 '.+\[id:\d+(,cd:\d+)?\]' 的充能层数超过 \d+", text)) == 10


def test_automation_only_lines(generated):
    """类型 70 共 46 条，渲染为映射表新增的说明行。"""
    _output_dir, files = outputs(generated)
    count = sum(path.read_text(encoding="utf-8").count(AUTOMATION_ONLY_LINE) for path in files)
    assert count == 46


def test_unknown_spell_placeholders(generated):
    """3 个缺失技能 ID 都渲染为 'Unknown Spell[id:<ID>]'，旧的 `(ID)` 写法归零，程序不中断。"""
    _output_dir, files = outputs(generated)
    text = "\n".join(path.read_text(encoding="utf-8") for path in files)
    for spell_id in UNKNOWN_SPELL_IDS:
        assert f"'Unknown Spell[id:{spell_id}]'" in text
        assert text.count(f"[id:{spell_id}]") == 1
    assert text.count("Unknown Spell[id:") == 3
    assert "Unknown Spell (" not in text


def test_cooldown_labels_in_generated_output(generated):
    """整库产物抽查：冷却 > 1 秒的标签带 cd（值为半进秒），无冷却的保持原样。

    期望值取自 12.1.0.69814 的 SpellCooldowns CSV：死神印记 45000ms、眼棱 30000ms、
    献祭光环 1500ms、嗜血 4500ms；瞄准射击 / 多重射击两列为 0。
    """
    _output_dir, files = outputs(generated)
    text = "\n".join(path.read_text(encoding="utf-8") for path in files)
    blood = (_output_dir / "deathknight" / "blood.txt").read_text(encoding="utf-8")
    assert "死神印记[id:439843,cd:45]" in blood
    assert "眼棱[id:198013,cd:30]" in text
    assert "献祭光环[id:258920,cd:2]" in text
    assert "嗜血[id:23881,cd:5]" in text
    assert "瞄准射击[id:19434]" in text and "瞄准射击[id:19434,cd" not in text
    assert "多重射击[id:257620]" in text and "多重射击[id:257620,cd" not in text


def test_run_is_offline_and_scans_data_tables_once(monkeypatch, tmp_path, csv_dir, condition_map_file):
    """整库运行：不建立任何网络连接，且 SpellName / SpellCooldowns 两张表都只打开扫描一次。"""
    import builtins
    import socket

    opened = {"SpellName": [], "SpellCooldowns": []}
    real_open = builtins.open

    def counting_open(file, *args, **kwargs):
        # 只统计两张数据表的打开次数（写输出文件也会走 open）
        name = Path(str(file)).name
        for table in opened:
            if name.startswith(f"{table}."):
                opened[table].append(str(file))
        return real_open(file, *args, **kwargs)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("本管线必须离线运行，不允许建立网络连接")

    monkeypatch.setattr(builtins, "open", counting_open)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)

    count = main.run(csv_dir=csv_dir, output_dir=str(tmp_path), condition_map_file=condition_map_file)
    assert count == 40
    for table, paths in opened.items():
        assert len(paths) == 1, f"{table} 表被打开了 {len(paths)} 次：{paths}"
