"""输出层：命名规则与整库生成结果（40 个文件 / 13 个职业目录 / 已知修正点计数）。"""

import re
from pathlib import Path

import main
from app import output

AUTOMATION_ONLY_LINE = "    automation only (not part of the game's Assisted Combat rotation)"
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
    """每个文件：首行 = 专精显示名（与文件名对应）；步骤编号从 0 连续；条件行 4 空格缩进。"""
    _output_dir, files = outputs(generated)
    for path in files:
        lines = path.read_text(encoding="utf-8").splitlines()
        assert lines, f"{path} 是空文件"
        assert lines[0].lower().replace(" ", "") == path.stem, f"{path} 首行与文件名不一致"
        numbers = []
        for line in lines[1:]:
            if ": Spell: " in line:
                assert re.match(r"^\d+: Spell: \S", line), f"{path}: 步骤行格式错误 {line!r}"
                numbers.append(int(line.split(":", 1)[0]))
            else:
                assert line.startswith("    ") and len(line) > 4, f"{path}: 条件行格式错误 {line!r}"
        assert numbers == list(range(len(numbers))), f"{path}: 步骤编号不连续 {numbers}"


def test_charge_lines_use_numbers(generated):
    """类型 63 共 10 条，全部输出数字层数，不再出现 'Spells' charges 或 'Charge Count' 当技能名。"""
    _output_dir, files = outputs(generated)
    text = "\n".join(path.read_text(encoding="utf-8") for path in files)
    assert "'Spells' charges" not in text
    assert "'Charge Count'" not in text
    assert len(re.findall(r"more than \d+ charges of spell '", text)) == 10


def test_automation_only_lines(generated):
    """类型 70 共 46 条，渲染为映射表新增的说明行。"""
    _output_dir, files = outputs(generated)
    count = sum(path.read_text(encoding="utf-8").count(AUTOMATION_ONLY_LINE) for path in files)
    assert count == 46


def test_unknown_spell_placeholders(generated):
    """3 个缺失技能 ID 都渲染为 'Unknown Spell (ID)'，程序不中断。"""
    _output_dir, files = outputs(generated)
    text = "\n".join(path.read_text(encoding="utf-8") for path in files)
    for spell_id in UNKNOWN_SPELL_IDS:
        assert f"'Unknown Spell ({spell_id})'" in text
    assert text.count("Unknown Spell (") == 3


def test_run_is_offline_and_scans_spell_table_once(monkeypatch, tmp_path, csv_dir, condition_map_file):
    """整库运行：不建立任何网络连接，且 SpellName 表只打开扫描一次。"""
    import builtins
    import socket

    opened = []
    real_open = builtins.open

    def counting_open(file, *args, **kwargs):
        # 只统计 SpellName 表的打开次数（写输出文件也会走 open）
        if Path(str(file)).name.startswith("SpellName."):
            opened.append(str(file))
        return real_open(file, *args, **kwargs)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("本管线必须离线运行，不允许建立网络连接")

    monkeypatch.setattr(builtins, "open", counting_open)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)

    count = main.run(csv_dir=csv_dir, output_dir=str(tmp_path), condition_map_file=condition_map_file)
    assert count == 40
    assert len(opened) == 1, f"SpellName 表被打开了 {len(opened)} 次：{opened}"
