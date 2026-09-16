"""项目入口：一次运行为全部有辅助战斗方案的专精生成 ``output/<职业>/<专精>.txt``。

用法（必须在仓库根目录执行，无命令行参数）：

    .venv\\Scripts\\python.exe main.py

流程：加载条件类型映射表 → 读取 ``csv_table/`` 下 5 张 DB2 导出表并构建
classes → specs → assist_plan → steps → rules 嵌套结构 → 收集本次需要的技能 ID →
单次流式扫描 SpellName 表建立技能名索引 → 逐专精渲染并写文件 → 打印进度与汇总。
技能名全部来自本地 CSV，运行过程不访问网络。
"""

import logging
import sys

from app import db2, output, render, spells

# ---- 全局配置（换游戏版本时只改这里） ----
VERSION = "12.1.0.69814"                      # 游戏客户端版本，决定 5 张表与 SpellName 的文件名
CSV_DIR = "csv_table"                         # DB2 导出表目录（相对仓库根目录）
OUTPUT_DIR = "output"                         # 生成结果目录
CONDITION_MAP_FILE = "ConditionTypeMap.csv"   # 条件类型 → 文本模板映射表
LOG_LEVEL = logging.WARNING                   # 调试时可改成 logging.INFO

_logger = logging.getLogger(__name__)


def setup_logging(loglevel):
    """配置日志输出（格式沿用旧版，输出到 stdout）。"""
    logging.basicConfig(
        level=loglevel,
        stream=sys.stdout,
        format="[%(asctime)s] %(levelname)s:%(name)s:%(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def build_spell_index(csv_dir, version, classes, condition_map):
    """收集本次需要的技能 ID 并单次扫描 SpellName 表，返回 ``(索引, 需求 ID 集合)``。"""
    steps = list(db2.iter_plan_steps(classes))
    required_ids = spells.collect_required_spell_ids(steps, condition_map)
    spell_table = f"{csv_dir}/{db2.table_filename('SpellName', version)}"
    spell_index = spells.read_spell_index(spell_table, required_ids)
    _logger.info(
        f"技能 ID：需要 {len(required_ids)} 个，SpellName 命中 {len(spell_index)} 个，"
        f"缺失 {len(required_ids) - len(spell_index)} 个"
    )
    return spell_index, required_ids


def run(csv_dir=CSV_DIR, output_dir=OUTPUT_DIR, condition_map_file=CONDITION_MAP_FILE, version=VERSION):
    """执行一次全量生成，返回写出的文件数（默认参数即全局配置）。"""
    setup_logging(LOG_LEVEL)
    condition_map = render.load_condition_map(condition_map_file)
    classes = db2.parse_and_build_db_dumps(csv_dir, version)
    spell_index, required_ids = build_spell_index(csv_dir, version, classes, condition_map)

    count = 0
    for class_name, spec_data in db2.iter_specs_with_plan(classes):
        spec_name = spec_data["Name"]
        body = render.render_rotation(condition_map, db2.spec_rotation(spec_data), spell_index)
        path = output.write_rotation(output_dir, class_name, spec_name, body)
        count += 1
        print(f"[{count}] {class_name} / {spec_name} -> {path}")

    print(f"共生成 {count} 个文件（技能名索引 {len(spell_index)} 个，需求 {len(required_ids)} 个）")
    return count


if __name__ == "__main__":
    run()
