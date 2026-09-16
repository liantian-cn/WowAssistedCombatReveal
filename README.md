# WowAssistedCombatReveal

把《魔兽世界》客户端 DB2 表导出的 CSV（辅助战斗 / 一键循环相关表）翻译成人类可读的
「技能优先级列表」文本。

项目**不连接游戏、不注入进程、运行时完全离线**：技能名来自本地 `csv_table/` 下的
SpellName 表（不再访问 Wowhead），一次运行即可为全部有辅助战斗方案的专精生成文本。

当前数据版本：`12.1.0.69814`（40 个方案 / 693 步 / 3116 条规则 / 13 个职业）。

## 用途与动机

- 借此对官方推荐循环提出改进建议；
- 看到「为什么它决定放这个技能」，从而更好地学习循环；
- 在「一键模式」与「手动技能」之间取舍，减少 GCD 损失。

## 环境准备

需要 Python 3.13（仓库内已带 `.venv`，按需重建）：

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

`requirements.txt` 里只有运行依赖 `pandas`；测试依赖 `pytest` 在该文件中以注释标明。

## 运行

在**仓库根目录**执行（`main.py` 无命令行参数，路径都是相对仓库根目录的）：

```powershell
.venv\Scripts\python.exe main.py
```

执行过程：读取 `ConditionTypeMap.csv` → 读取 `csv_table/` 下 5 张 12.1.0.69814 的 CSV →
单次流式扫描 `SpellName.12.1.0.69814.csv` 建立技能名索引 → 逐专精渲染并写入
`output/<职业小写无空格>/<专精小写无空格>.txt`（40 个文件 / 13 个职业目录）。

换游戏版本时改 `main.py` 顶部的全局变量即可：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `VERSION` | `12.1.0.69814` | 决定 5 张表与 SpellName 的文件名 |
| `CSV_DIR` | `csv_table` | DB2 导出表目录 |
| `OUTPUT_DIR` | `output` | 生成结果目录 |
| `CONDITION_MAP_FILE` | `ConditionTypeMap.csv` | 条件类型 → 文本模板映射表 |
| `LOG_LEVEL` | `logging.WARNING` | 调试时可改成 `logging.INFO` |

## 测试

```powershell
.venv\Scripts\python.exe -m pytest tests -q
```

## 输出格式

每个文件 = 首行专精显示名 + 步骤块（行结构与旧版 `out/*.txt` 一致；本期起技能名后追加
`[id:<spellID>]`，文本不再与旧产物逐字节相同）。
下面片段原样复制自 `output/hunter/marksmanship.txt`（仅中间步骤用省略号跳过）：

```
Marksmanship
0: Spell: Multi-Shot[id:257620]
    if talent 'Multi-Shot[id:257620]' is taken
    if player has resources to cast spell 'Multi-Shot[id:257620]'
    if spell 'Multi-Shot[id:257620]' is off cooldown
    if spell 'Multi-Shot[id:257620]' is within allowed range
    if player has buff/debuff 'Trick Shots[id:257622]' with at least 2000 ms left
    if there are more than 3 targets within 10 yards of target
1: Spell: Multi-Shot[id:257620]
    if talent 'Multi-Shot[id:257620]' is taken
    ...
（中间步骤略）
12: Spell: Aimed Shot[id:19434]
    if talent 'Aimed Shot[id:19434]' is taken
    if player has resources to cast spell 'Aimed Shot[id:19434]'
    if spell 'Aimed Shot[id:19434]' is off cooldown
    if spell 'Aimed Shot[id:19434]' is within allowed range
    if spell 'Aimed Shot[id:19434]' can be successfully cast
    if player has more than 2 charges of spell 'Aimed Shot[id:19434]'
```

- 首行的专精名由输出层显式写入（旧版是 `find_rotation` 里调试 `print` 的副产物）；
- `N` 从 0 开始，是对方案步骤的遍历序号，**与游戏内 `OrderIndex` 无关**（见下节）；
- **由 spellID 解析出的名称一律带 `[id:<spellID>]` 后缀**：步骤标题（不加引号）、`{spell}`
  占位符、Spell 型条件参数（技能 / 光环 / 天赋，单引号包裹）都适用，便于把文本与 DB2 的
  技能 ID 直接对照；SpellName 表里查不到名称时输出 `Unknown Spell[id:<spellID>]`；
- 数值型参数不受影响（层数、距离、百分比、毫秒等，如 `more than 2 charges of spell`、
  `within 10 yards`、`50% health`），这些数字后面不会出现 `[id:`；
- 条件行固定 4 空格缩进，模板来自 `ConditionTypeMap.csv`；
- 文件编码 UTF-8（无 BOM）、换行 CRLF，与旧产物一致。

## 仓库结构

```
main.py                  # 唯一入口：全局配置 + 全量生成编排
app/
  db2.py                 # 5 张 CSV → classes/specs/plan/steps/rules 嵌套结构
  spells.py              # SpellName 表单次流式扫描，建立技能名索引
  render.py              # 条件映射表 + 模板渲染
  output.py              # 命名规则与写文件
csv_table/               # DB2 导出 CSV（必需的 5 张表 + enUS/zhCN 两份 SpellName；
                         # 另含本期未使用的 SpellCooldowns.12.1.0.69814.csv，为后续阶段预置）
output/                  # 生成结果（40 个文件，按项目约定入库）
tests/                   # pytest 测试
ConditionTypeMap.csv     # 条件类型 → 文本模板（人工维护）
PROJECT_LOGIC.md         # 数据流、模块职责、已知问题（详细文档）
```

## 数据来源

`csv_table/` 中的表全部来自 [wago.tools](https://wago.tools) 的 DB2 CSV 导出
（`AssistedCombat`、`AssistedCombatRule`、`AssistedCombatStep`、`ChrClasses`、
`ChrSpecialization`、`SpellName`，build `12.1.0.69814`）。`SpellName` 目前只使用 enUS，
zhCN 文件留在 `csv_table/` 中，后续再接入。
`csv_table/` 另含一张本期未使用的 `SpellCooldowns.12.1.0.69814.csv`（用户预置，供后续阶段使用）。

## 已知限制

输出顺序是 CSV 行序而不是游戏内优先级顺序、模板用 `eval` 渲染、部分条件类型的参数语义
尚未确认等，详见 [PROJECT_LOGIC.md](PROJECT_LOGIC.md) 的「已知问题」章节。

## 许可与致谢

本项目使用 MIT 许可，见 [LICENSE.txt](LICENSE.txt)。

原始作者：**Shawn McNaughton**（[@shawngmc](https://github.com/shawngmc)）。
本仓库是他的 `wow_assist_mapper` 思路的延续：把辅助战斗数据翻译成可读文本；
第一期重构只调整工程结构（`main.py` + `app/`、离线技能名、可测试），输出行为与旧版保持一致；
第二期起由 spellID 解析出的技能名统一追加 `[id:<spellID>]` 标签，输出文本因此不再与旧版逐字节相同。
