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

实施者：Developer（子代理），实施日期 2026-09-17，基线提交 `6f5ac07`。
所有命令均在仓库根目录执行，`python` 一律为 `.venv\Scripts\python.exe`，无网络访问。

### 1. 命令与退出码

| # | 命令 | 退出码 | 关键输出 |
| --- | --- | --- | --- |
| 1 | `.venv\Scripts\python.exe main.py` | 0 | 40 行 `[N] 职业 / 专精 -> output\...`，末行 `共生成 40 个文件（技能名索引 548 个，需求 551 个）`；`SpellName 表中缺少 3 个技能 ID：[194310, 389387, 470058]`（WARNING，与第一期一致） |
| 2 | `.venv\Scripts\python.exe -m pytest tests -q` | 0 | `26 passed in 2.06s`（第一期 22 个用例 → 本期 26 个：新增 4 个，未删减既有覆盖点） |
| 3 | `.venv\Scripts\python.exe .script\verify_spell_labels.py` | 0 | `old-vs-new identical except labels: 40/40 (legacy placeholders rewritten: 3)`；`labels total=3431 checked=3431 lines=3809`；`unknown labels=3 old style=0`；`problems=0`（报告：`.script/verify_spell_labels_report.txt`） |
| 4 | `.venv\Scripts\python.exe .script\verify_docs_examples.py` | 0 | 映射表自检 `含危险字符的行: []` / `计划外花括号: []`；README 示例 17 行与 `output/hunter/marksmanship.txt` 逐行按序一致 |
| 5 | `Get-ChildItem -Recurse -File output\*.txt` / `-Directory output` | 0 | 40 个文件 / 13 个职业目录 |

### 2. 计数与差异范围（脚本 3，独立于 `app/` 实现读取 CSV）

- `[id:` 标签 **3431** 处 = 步骤标题 693 + 条件行 2738；全量核对 3431/3431，问题 **0**；
- `Unknown Spell[id:` **3** 处（194310 / 389387 / 470058 各 1 处）；旧写法 `Unknown Spell (` **0** 处；
- **非技能参数未改动的强证据**：把新产物的全部 `[id:N]` 去掉、并把旧产物中 3 处 `Unknown Spell (ID)` 归一为 `Unknown Spell` 之后，40/40 个文件与改动前的产物**逐字节一致**——即除标签外（含数字、缩进、编号、顺序、空行）没有任何文本变化；
- 逐行核对规则：按"步骤标题行 + 该步每条条件行"顺序走完 40 个文件共 3809 行，核对每行的 `[id:]` 集合
  与 `AssistedCombatStep.SpellID` / `AssistedCombatRule` 中 Spell 型 `ConditionValueN` 一致（模板只引用被渲染的占位符），
  且每个 ID 旁渲染出的名称与脚本自行读取的 `SpellName` 表一致。

### 3. 抽样核对明细（7 条，节选自报告 A/B/C 三组各 16 条）

| 输出行（相对路径:行号） | 源数据出处（脚本核对） | ID → SpellName 表内名称 |
| --- | --- | --- |
| `hunter/marksmanship.txt:70` `12: Spell: Aimed Shot[id:19434]` | 步骤标题：step 12，`AssistedCombatStep.SpellID=19434` | 19434 → Aimed Shot |
| `monk/windwalker.txt:38` `if spell 'Whirling Dragon Punch[id:152175]' is off cooldown` | 条件行：step 5，rule 19613（ConditionType=2，`{spell}`） | 152175 → Whirling Dragon Punch |
| `demonhunter/havoc.txt:21` `if player has buff/debuff 'Reaver's Glaive[id:444686]'` | 条件行：step 2（SpellID=185123），rule 21543（ConditionType=9，`Spell:Buff` 参数） | 444686 → Reaver's Glaive |
| `rogue/outlaw.txt:141` `if spell 'Between the Eyes[id:315341]' is on cooldown` | 条件行：step 22（SpellID=1277933），rule 85923（ConditionType=1，`Spell` 参数） | 315341 → Between the Eyes |
| `warrior/arms.txt:3` `if target does not have buff/debuff 'Rend[id:388539]'` | 条件行：step 0（SpellID=845），rule 1180（ConditionType=15，参数 388539 仅作规则参数出现） | 388539 → Rend |
| `priest/shadow.txt:108` `if talent 'Shadow Word: Madness[id:335467]' is taken` | 条件行：step 20，rule 37695（ConditionType=0，`{spell}`） | 335467 → Shadow Word: Madness |
| `deathknight/unholy.txt:50` `if target has buff/debuff 'Unknown Spell[id:194310]'` | 条件行：step 8（SpellID=55090），rule 4828（ConditionType=10，`Spell:Buff` 参数 194310） | 194310 → 表中缺失，按约定占位 |

### 4. Acceptance 1–8 逐条结果

1. **通过**：3431 处由 spellID 解析出的名称全部带 `[id:<十进制>]`；标题形如 `0: Spell: Multi-Shot[id:257620]`，条件形如 `if talent 'Multi-Shot[id:257620]' is taken`（脚本 3 全量核对 + pytest 计数断言）。
2. **通过**：`'Unknown Spell[id:194310]'` / `[id:389387]` / `[id:470058]` 各精确 1 处；`Unknown Spell (` 0 处；`pytest tests/test_output.py::test_unknown_spell_placeholders` 与 `tests/test_spells.py` 断言标签格式。
3. **通过**：非技能参数不变（40/40 文件去标签后逐字节一致）；`if player has less than 50% health`（`output/deathknight/blood.txt:86`）、`if there are more than 3 targets within 10 yards of target`、`if player has more than 2 charges of spell 'Aimed Shot[id:19434]'`（pytest 断言无 `[id:2]`）。
4. **通过**：行结构未变——`test_output_file_structure` 校验 40 个文件首行专精名、编号从 0 连续、条件行 4 空格缩进；脚本 3 按行数一一对应走完全部 3809 行；零规则步骤仍只有标题行（39 个零规则步骤，如 `hunter/marksmanship.txt:77` 的 `13: Spell: Steady Shot[id:56641]` 与 `:78` 的 `14: Spell: Arcane Shot[id:185358]`）。
5. **通过**：抽样 7 条（上表）+ 报告 16 条，ID 与 `AssistedCombatStep` / `AssistedCombatRule` + `SpellName` 的对应关系全部一致。
6. **通过**：`pytest` 26 passed；`main.py` 退出码 0、40 文件 / 13 目录；`test_run_is_offline_and_scans_spell_table_once` 通过（无网络连接、SpellName 只扫描 1 次）。
7. **通过**：README 示例改为真实产物片段并经脚本逐行核对；PROJECT_LOGIC 第 4.4 / 7.3 / 7.4 / 8 / 8.1 / 8.2 / 9 节同步新格式；仓库内 `Unknown Spell (` 旧描述仅保留在第一期计划文件（历史记录）。
8. **待 PuttyCoder 执行**：按任务边界，Developer 未做任何 Git 写操作；当前工作区 47 个改动（40 个 `output/` + `app/render.py`、`app/spells.py`、3 个测试文件、README、PROJECT_LOGIC）。

### 5. 实现说明与需知悉的偏差

- `render_rule()` 的第三个参数由 `spell_name` 改为 `spell_id`（内部调用 `labelled()`）：计划 Decisions 5 要求三处都经统一入口取名称，传 ID 可保证同一 ID 的标题行与条件行名称/标签必然一致；测试调用点已同步（4 处），无外部调用者。
- `SpellIndex.display_name()` 保留（返回不带标签的裸名称，供 `labelled()` 与后续需要纯名称的场景使用）；`UNKNOWN_SPELL_NAME` 常量改为 `"Unknown Spell"`。
- 未改动 `ConditionTypeMap.csv`、`app/db2.py`、`app/output.py`、`main.py` 与行结构/顺序；未处理第一期遗留问题（类型 9/13 参数语义等）。
- 验证脚本 `.script/verify_spell_labels.py` 与报告为该机一次性核对用，`.script/` 已被 `.gitignore` 排除，不入库。

## Review Notes

### Round 1（全量复核，审计范围：`app/spells.py`、`app/render.py`、`tests/test_spells.py`、`tests/test_render.py`、`tests/test_output.py`、`README.md`、`PROJECT_LOGIC.md`、`output/**`）

- 结论：**无 Blocker / Major / Minor**；Acceptance 1–5、7 由 Reviewer 独立证据判定为通过；Acceptance 6（pytest 退出码、main.py 进程行为）因 Reviewer 会话 shell 权限拒绝运行 python，未能独立执行，改用磁盘产物与用例内容核对（用例数 22→26、40 文件 / 13 目录、无 BOM / 无空白错误）；Acceptance 8（提交）由 PuttyCoder 执行。
- Reviewer 独立核对的关键事实：
  - `[id:` 共 3431 处 = 693 标题 + 2738 条件行；`git diff --numstat` 显示 each-file added == deleted（纯插入，无增删行）；无一行出现两个标签；无 `[id:0]`、无空格变体、无补零变体。
  - 693 个标题行全部以 `]` 结尾；40 个文件首行仍为纯专精名（无标签）；缩进恒为 4 空格、无空行、编号从 0 连续。
  - 名称 ↔ ID 逐条抽查（19434 Aimed Shot、152175 Whirling Dragon Punch、444686 Reaver's Glaive、315341 Between the Eyes、388539 Rend、335467 Shadow Word: Madness、703 Garrote、55090 Scourge Strike、1277933 Preparation、257622 Trick Shots 等）全部与 `SpellName` 表一致；按 CSV 行序对 plan 89/332/327/328/4 全量核对标题 ID 均正确；`{spell}` 行的 ID 与同一步骤标题一致；`{argN}` 行的 ID 与对应规则列一致（含 `20517` 的 257622 + 2000ms、`64722` 的 55078、`34176/34181` 的 263165）。
  - 非技能参数未受影响：`%[id:`、`yards[id:`、`ms[id:`、`charges[id:`、`stacks[id:`、`targets[id:` 均 0 命中；word-diff 显示每处差异都是 `名称` → `名称[id:N]`（含 `Unknown Spell (194310)` → `Unknown Spell[id:194310]`）。
  - 旧占位写法在 `output/` 内 0 命中；3 个缺失 ID 各恰好 1 处（unholy / mistweaver / enhancement）。
  - README 示例逐行按序存在于 `output/hunter/marksmanship.txt`；PROJECT_LOGIC 的 `display_name` / `labelled` 职责、`render_rule` 签名、3431 = 693 + 2738 计数与实现一致。
- 新增 1 条 Suggestion（按规则不阻塞交付，记录为残留项，未触发返工）：
  - **S1（测试加固）**：`tests/test_output.py` 的标签计数用例是聚合断言（总数 + ID 集合 ⊆ required_ids），能抓住多标/漏标，但抓不住"标题或 `{spell}` 用错 ID"这类回归；建议把标题 ID 与 `db2` 取到的步骤 `SpellID` 按文件顺序一一比对（几行代码）。当前实际产物经 Reviewer 抽样与全量核对均正确。
- 备注（非发现）：类型 13 的 6 行仍输出裸数字（第一期遗留，计划 Scope 明确不修，PROJECT_LOGIC 10.4 已记录）；若将来数据在 spell 型 `ValueN` 上出现 0，会渲染 `Unknown Spell[id:0]`（当前数据不存在）。
- Reviewer 未修改任何文件、未执行 git 写操作。

## Completion

- **交付内容（本任务）**：`app/spells.py`（`UNKNOWN_SPELL_NAME` 改为 `Unknown Spell`；新增 `SpellIndex.labelled()` 统一产出 `名称[id:<十进制 spellID>]`，`display_name()` 保留裸名称）、`app/render.py`（三处名称来源全部改走 `labelled()`，`render_rule` 第三参数由名称改为步骤 ID）、`tests/`（22 → 26 用例，覆盖标签格式 / 未命中占位 / 数值参数不带标签 / 全量标签计数）、`README.md` 与 `PROJECT_LOGIC.md` 同步、`output/**` 40 个文件重新生成（3431 处标签）。
- **提交**：`6f5ac07` 计划基线；实现提交（本次，含计划 Review Notes 与完成记录）。
- **验收状态**：计划 Acceptance 1–8 满足；其中 1–5、7 由 Reviewer 独立证据判定，6 的执行类证据来自 Developer（`main.py` 退出码 0 / 40 文件 13 目录 / `pytest` 26 passed）并经 Reviewer 以产物与用例内容交叉核对，8 由 PuttyCoder 完成提交。
- **残留风险与未做项**：S1 测试加固建议未处理（不影响当前正确性）；第一期遗留项（zhCN 未接入、类型 9/13 参数语义、输出按 CSV 行序、`eval` 模板渲染）保持不变；spell 型参数出现 0 值时会输出 `Unknown Spell[id:0]`（当前数据不触发）。
