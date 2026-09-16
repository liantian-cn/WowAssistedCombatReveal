"""wow_assist_mapper 的逻辑模块包。

职责划分：
- ``db2``：读取 5 张 DB2 导出 CSV，构建 classes → specs → assist_plan → steps → rules 嵌套结构；
- ``spells``：单次流式扫描 SpellName 表，建立"本次需要"的技能 ID → 技能名索引；
- ``render``：条件类型映射表与文本渲染（模板 + 4 空格缩进条件行）；
- ``output``：输出目录/文件命名规则与写文件。
"""
