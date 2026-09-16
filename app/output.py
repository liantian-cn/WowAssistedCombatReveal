"""输出层：目录/文件命名规则与写文件。

命名规则沿用旧版 ``run_all.ps1`` 的产物：职业、专精名小写并去掉空格，
例如 ``Death Knight`` → ``output/deathknight/``，专精 ``Beast Mastery`` → ``beastmastery.txt``。

旧产物由 PowerShell 重定向生成，字节形态是 UTF-8（无 BOM）+ CRLF 换行 + 末尾换行；
这里用 ``newline="\\r\\n"`` 显式保持同样的换行，避免新旧比对时每行都不同。
"""

import os
from pathlib import Path


def class_directory_name(class_name):
    """职业显示名 → 输出目录名（小写、去空格）。"""
    return class_name.lower().replace(" ", "")


def spec_file_name(spec_name):
    """专精显示名 → 输出文件名（小写、去空格、``.txt`` 后缀）。"""
    return spec_name.lower().replace(" ", "") + ".txt"


def write_rotation(output_dir, class_name, spec_display_name, body):
    """写入 ``output/<职业>/<专精>.txt``：首行专精显示名 + 渲染正文，返回写入路径。

    首行过去是 ``find_rotation`` 里一句调试 ``print`` 的副产物，现在由本函数显式写入。
    """
    directory = os.path.join(output_dir, class_directory_name(class_name))
    os.makedirs(directory, exist_ok=True)
    path = Path(directory) / spec_file_name(spec_display_name)
    content = spec_display_name + "\n"
    if body:
        content += body + "\n"
    with open(path, "w", encoding="utf-8", newline="\r\n") as handle:
        handle.write(content)
    return path
