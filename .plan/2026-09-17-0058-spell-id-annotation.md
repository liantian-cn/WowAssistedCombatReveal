# 第二期改动：所有技能名后追加 `[id:<spellID>]`

## Prompt

用户原始请求（逐字）：

> 修改，为那些spellid转化回来的技能、光环、天赋后面，加入中括号。内部写id:spellid
>
> 比如
>
> ```
> 0: Spell: Reaper's Mark[id:xxxxxx]
>     if talent 'Reaper's Mark[id:xxxxxx]' is taken
>     if player has resources to cast spell 'Reaper's Mark[id:xxxxxx]'
>     if spell 'Reaper's Mark[id:xxxxxx]' is off cooldown
>     if target does not have buff/debuff 'Reaper's Mark[id:xxxxxx]'
>     if spell 'Reaper's Mark[id:xxxxxx]' is within allowed range
>
> 15: Spell: Death Strike[id:xxxxxx]
>     if talent 'Death Strike[id:xxxxxx]' is taken
>     if player has resources to cast spell 'Death Strike[id:xxxxxx]'
>     if spell 'Death Strike[id:xxxxxx]' is off cooldown
>     if spell 'Death Strike[id:xxxxxx]' is within allowed range
>     if player has less than 50% health
> ```

## Question

### 第 1 轮（2 问）

1. **`SpellName` 表里查不到的 ID（本数据 3 个：194310 / 389387 / 470058）怎么写？** → 改为 `Unknown Spell[id:194310]`（不再使用旧的 `Unknown Spell (194310)` 括号写法，与其他名称统一为 `名称[id:<spellID>]`）。
2. **中括号里的数字格式？** → 原样十进制输出，不补零（`[id:43265]`）。

### 前置事实（Agent 在仓库中核对，非提问）

- 当前名称产生的三处代码位置（`app/render.py`）：
  1. `render_rotation`：步骤标题行 `` f"{step_index}: Spell: {spell_name}" ``（名称来自该步 `SpellID`）；
  2. `render_rule`：模板变量 `spell`（同一技能名，用于 `{spell}` 占位符的条件行）；
  3. `_resolve_value`：`ValueN` 以 "spell" 开头的条件参数（技能/光环/天赋，含 `Spell:Buff`、`Spell Charges` 之外的列）解析为技能名。
- 名称解析集中在 `app/spells.py::SpellIndex`：`display_name()` 命中返回表内名称，未命中返回 `UNKNOWN_SPELL_NAME`（现为 `"Unknown Spell ({spell_id})"`）。
- 非技能参数（如 `50`、`10`、`3000`）不经过技能名解析，不带 ID。
- 步骤本身零规则（如 Blood DK 的 Death and Decay）只有标题行，改动后其标题也会带 ID。

## Goal

在生成文本中，凡是**由 spellID 解析出来的名称**（步骤技能、`{spell}` 占位符、Spell 型条件参数：技能 / 光环 / 天赋）一律追加 `[id:<spellID>]` 后缀；查不到名称时输出 `Unknown Spell[id:<spellID>]`。数值型条件参数与其它文本保持不变。

## Scope

In：

- `app/spells.py`：新增"名称 + ID 标签"的统一格式化入口；未命中占位改为 `Unknown Spell`（ID 由标签统一附带）。
- `app/render.py`：步骤标题行、`{spell}` 变量、`_resolve_value` 三处改用新格式化入口。
- 重新生成 `output/`（40 个文件）。
- 同步更新 `tests/`（含 3 处 `Unknown Spell (ID)` 期望值）、`README.md` 示例、`PROJECT_LOGIC.md` 中的格式说明与示例。
- 计划文件新增本任务记录（不改动第一期计划内容）。

Out：

- 不改变步骤/条件行的结构、缩进、编号与顺序（仍为 CSV 行序）。
- 不改变非技能参数的渲染（如 `%`、yards、ms、资源数量）。
- 不做 ID 到链接/图标等其它扩展；不接入 zhCN；不修正第一期记录的遗留问题（类型 9/13 参数语义等）。

## Decisions

1. **统一格式**：`<名称>[id:<spellID>]`，ID 为十进制原值、不补零、不加空格；中括号与名称之间无空格。
2. **适用位置**：三处全改——步骤标题行（`N: Spell: <名称>[id:…]`）、规则中 `{spell}` 展开处、`ValueN` 以 spell 开头的参数（含 aura / talent / charges / cooldown 相关类型）。
3. **未命中占位**：`Unknown Spell[id:<spellID>]`（整体替换旧写法 `Unknown Spell (ID)`）；括号内不再重复 ID。
4. **引号规则不变**：条件参数仍用单引号包裹（`'名称[id:…]'`），步骤标题行不加引号。
5. **实现方式**：`SpellIndex` 提供统一格式化方法（例如 `labelled(spell_id)`）返回 `f"{name}[id:{int(spell_id)}]"`，`render_rotation` / `render_rule` / `_resolve_value` 均通过它取名称；`display_name()` 保留（返回不带标签的裸名称，供需要纯名称的场景使用）。
6. **产物与文档同步**：`output/` 全部重新生成并入库；README 的示例片段、PROJECT_LOGIC 的渲染说明与本任务的验收口径同步更新。
7. **验收口径变更说明**：第一期"输出与旧 `out/` 格式完全一致"的要求被本任务**有意修订**（新增 ID 后缀），旧格式的一致性不再作为本期验收项；第一期计划文件保持原样，仅在本计划中记录该变更。

## Implementation Steps

1. 修改 `app/spells.py`：占位常量改为 `Unknown Spell`；新增统一格式化方法（命中/未命中都返回 `名称[id:N]`）。
2. 修改 `app/render.py`：步骤标题、`{spell}` 变量、`_resolve_value` 改用统一格式化方法；同步更新模块 docstring 中对占位写法的描述。
3. 更新测试：`tests/test_spells.py`（标签格式、未命中占位）、`tests/test_render.py`（标题行与条件行的 ID 后缀、非技能参数不带 ID）、`tests/test_output.py`（结构断言适配新格式；`Unknown Spell`/`[id:` 计数断言）。保持既有用例的覆盖点不减少。
4. 重新生成 `output/`：`.venv\Scripts\python.exe main.py`。
5. 更新文档：`README.md`（输出示例改为含 ID 的真实片段）、`PROJECT_LOGIC.md`（第 7 节渲染说明、第 8 节输出格式、示例与"已知问题"中相关描述）。
6. 自测与证据：运行 main.py 与 pytest；统计 `[id:` 数量、`Unknown Spell[id:` 数量（应为 3），抽样核对若干规则的 ID 与 CSV 一致；确认非技能参数行未被改动。
7. 提交：计划基线提交 + 实现提交（沿用两段式）。

## Acceptance Criteria

1. `output/` 40 个文件中，**每一处由 spellID 解析出的名称**都带 `[id:<数字>]` 后缀；步骤标题形如 `0: Spell: Reaper's Mark[id:127793]`，条件形如 `if talent '…[id:…]' is taken`。
2. 3 个查不到的 ID 精确渲染为 `Unknown Spell[id:194310]`（`[id:194310]` 仅出现一次，不再有 `Unknown Spell (194310)` 形式）。
3. 非技能参数保持不变：如 `if player has less than 50% health`、`if there are more than 3 targets within 10 yards of player`、`if player has more than 2 charges of spell '…[id:…]'`（其中数字部分无 `[id:`）。
4. 行结构不变：首行专精显示名、`N: Spell: …` 编号从 0 连续、条件行 4 空格缩进、无空行；步骤顺序仍为 CSV 行序；零规则步骤仍只有标题行（标题带 ID）。
5. 抽样核对：随机抽取 ≥5 条含 ID 的行，其 ID 与该行文本在 `AssistedCombatStep` / `AssistedCombatRule` + `SpellName` 中的对应关系一致（同一 ID 的名称与表内名称一致）。
6. `.venv\Scripts\python.exe -m pytest tests -q` 全部通过；`main.py` 退出码 0、无网络访问、仍生成 40 文件 / 13 目录。
7. 文档同步：README 示例与 PROJECT_LOGIC 的格式说明反映新格式，且不再出现 `Unknown Spell (ID)` 的旧描述（历史记录性文字除外）。
8. `git status` 干净，两次提交（计划基线 + 实现）完成。

## Verification

（实现完成后由 Developer 填写：命令、退出码、关键输出、计数与抽样核对结果）

## Review Notes

（Reviewer 结论与处置记录）

## Completion

（最终交付记录、提交哈希、残留风险）
