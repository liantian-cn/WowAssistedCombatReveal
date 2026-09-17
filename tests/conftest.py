"""pytest 公共配置与共享夹具。

本仓库是脚本型项目（没有安装成包），因此先把仓库根目录加入 ``sys.path``；
所有数据路径都用 ``ROOT`` 拼成**绝对路径**，这样无论从哪个目录启动 pytest 都能跑。
夹具为会话级，避免每个测试重复扫描 11MB 的 SpellName 表与 1MB 的 SpellCooldowns 表。
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main  # noqa: E402  根目录入口脚本，测试直接复用其全局配置
from app import cooldowns, db2, render, spells  # noqa: E402


@pytest.fixture(scope="session")
def repo_root():
    """仓库根目录（测试不使用相对路径，避免依赖 pytest 的启动目录）。"""
    return ROOT


@pytest.fixture(scope="session")
def csv_dir():
    """``csv_table/`` 的绝对路径。"""
    return str(ROOT / main.CSV_DIR)


@pytest.fixture(scope="session")
def condition_map_file():
    """条件类型映射表的绝对路径。"""
    return str(ROOT / main.CONDITION_MAP_FILE)


@pytest.fixture(scope="session")
def condition_map(condition_map_file):
    """条件类型映射表（12.1 数据使用的 55 种类型 + 其余说明行，共 71 行）。"""
    return render.load_condition_map(condition_map_file)


@pytest.fixture(scope="session")
def classes(csv_dir):
    """classes → specs → assist_plan → steps → rules 嵌套结构。"""
    return db2.parse_and_build_db_dumps(csv_dir, main.VERSION)


@pytest.fixture(scope="session")
def plan_steps(classes):
    """全部方案的步骤列表（CSV 行序）。"""
    return list(db2.iter_plan_steps(classes))


@pytest.fixture(scope="session")
def required_spell_ids(plan_steps, condition_map):
    """本次渲染需要的技能 ID（步骤技能 + Spell 型规则参数，去 0）。"""
    return spells.collect_required_spell_ids(plan_steps, condition_map)


@pytest.fixture(scope="session")
def cooldown_index(csv_dir, required_spell_ids):
    """技能冷却索引（只含所需 ID），整个测试会话只扫描一次 SpellCooldowns 表。"""
    cooldown_table = Path(csv_dir) / db2.table_filename("SpellCooldowns", main.VERSION)
    return cooldowns.read_cooldown_index(cooldown_table, required_spell_ids)


@pytest.fixture(scope="session")
def spell_index(csv_dir, required_spell_ids, cooldown_index):
    """``(技能名索引, 需求 ID 集合)``，整个测试会话只扫描一次 SpellName 表；索引带冷却信息。"""
    spell_table = Path(csv_dir) / db2.table_filename("SpellName", main.VERSION)
    index = spells.read_spell_index(spell_table, required_spell_ids, cooldown_index)
    return index, required_spell_ids


@pytest.fixture(scope="session")
def generated(tmp_path_factory, csv_dir, condition_map_file):
    """整库生成一次到临时目录，返回 ``(输出目录, run() 返回值)``。"""
    output_dir = tmp_path_factory.mktemp("generated_output")
    count = main.run(csv_dir=csv_dir, output_dir=str(output_dir), condition_map_file=condition_map_file)
    return output_dir, count
