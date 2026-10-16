#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把本机 skill 源同步进仓库副本（`skills/luoshui-report-template/`）。

背景
----
skill 的**权威源**只在本机 `~/.workbuddy/skills/luoshui-report-template/`；
仓库里那份 `skills/luoshui-report-template/` 是**只读备份**，目的是换机后能直接编辑、
并且能看 git 历史。两边一旦走散就会出现「改了半天发现改的是仓库副本、线上 skill 没变」这种事故。

方向铁律
--------
**本机 → 仓库**（单向）。**永远不要反向覆盖** —— 本机那份是权威。
所以本脚本没有 `--reverse`，也不接受把仓库当源。

用法
----
    python3 build/sync_skill_src.py            # 干跑：只比对，打印差异，不写任何文件
    python3 build/sync_skill_src.py --go       # 真同步（会写仓库副本）
    python3 build/sync_skill_src.py --go --skill-dir /path/to/other/skill

退出码: 0 = 一致（或 `--go` 成功）；1 = 有差异（干跑模式）/ 出错。

配合
----
`build/verify_skill_package.py` 校验的是**打包件**能不能被客户端导入；
本脚本管的是**源**在不在仓库、新不新。两个一起跑才完整。
"""

import argparse
import filecmp
import os
import shutil
import sys

# ── 默认路径 ────────────────────────────────────────────────
HOME = os.path.expanduser("~")
DEFAULT_SRC = os.path.join(HOME, ".workbuddy", "skills", "luoshui-report-template")
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DST = os.path.join(REPO_ROOT, "skills", "luoshui-report-template")

# 不纳入仓库的东西：macOS 垃圾文件 + 打包/缓存产物
SKIP_NAMES = {".DS_Store", "Thumbs.db", "desktop.ini", "__pycache__"}
SKIP_SUFFIX = (".pyc", ".pyo", ".bak")


def rel_files(root):
    """列出 root 下应当纳入的所有文件（相对路径，POSIX 分隔符），已排序。"""
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        # 就地剪枝，避免走进 __pycache__ 之类
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_NAMES)
        for fn in sorted(filenames):
            if fn in SKIP_NAMES or fn.endswith(SKIP_SUFFIX):
                continue
            full = os.path.join(dirpath, fn)
            out.append(os.path.relpath(full, root).replace(os.sep, "/"))
    return sorted(out)


def compare(src, dst):
    """返回 (added, changed, same, removed) 四组相对路径。"""
    s = rel_files(src)
    d = rel_files(dst) if os.path.isdir(dst) else []
    added, changed, same = [], [], []
    for r in s:
        tf = os.path.join(dst, r.replace("/", os.sep))
        if r not in d:
            added.append(r)
        elif not os.path.isfile(tf):
            added.append(r)
        elif filecmp.cmp(os.path.join(src, r.replace("/", os.sep)), tf, shallow=False):
            same.append(r)
        else:
            changed.append(r)
    removed = [r for r in d if r not in set(s)]
    return added, changed, same, removed


def fmt(nbytes):
    if nbytes < 1024:
        return "%d B" % nbytes
    if nbytes < 1024 * 1024:
        return "%.1f KB" % (nbytes / 1024.0)
    return "%.2f MB" % (nbytes / 1024.0 / 1024.0)


def total_size(base, rels):
    n = 0
    for r in rels:
        p = os.path.join(base, r.replace("/", os.sep))
        if os.path.isfile(p):
            n += os.path.getsize(p)
    return n


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--go", action="store_true", help="真同步（默认只干跑）")
    ap.add_argument("--skill-dir", default=DEFAULT_SRC, help="本机 skill 源目录")
    ap.add_argument("--repo-dir", default=DEFAULT_DST, help="仓库内副本目录")
    a = ap.parse_args()

    src, dst = os.path.abspath(os.path.expanduser(a.skill_dir)), os.path.abspath(a.repo_dir)
    print("=" * 68)
    print("源（权威，只读）:", src)
    print("目标（仓库副本）:", dst)
    print("-" * 68)

    if not os.path.isdir(src):
        print("✗ 源目录不存在 —— 先确认 skill 装在哪")
        return 1

    added, changed, same, removed = compare(src, dst)

    for tag, mark_, group in (("新增", "+", added), ("内容不同", "~", changed)):
        for r in group:
            print("  %s %s" % (mark_, r))
    for r in removed:
        print("  - %s   ← 只存在于仓库副本（源里已删）" % r)
    print("-" * 68)
    print("新增 %d · 更新 %d · 一致 %d · 多余 %d" % (len(added), len(changed), len(same), len(removed)))
    print("源体积 %s → 副本现有 %s"
          % (fmt(total_size(src, rel_files(src))), fmt(total_size(dst, rel_files(dst)))))

    dirty = bool(added or changed or removed)
    if not dirty:
        print("⇒ ✓ 已一致，无需同步")
        return 0

    if not a.go:
        print("⇒ 有差异（干跑，未写任何文件）。加 --go 执行同步。")
        return 1

    # ── 真同步：镜像式覆盖（不含删除，删除只提示）────────────
    for r in added + changed:
        sp = os.path.join(src, r.replace("/", os.sep))
        dp = os.path.join(dst, r.replace("/", os.sep))
        os.makedirs(os.path.dirname(dp), exist_ok=True)
        shutil.copy2(sp, dp)
    print("⇒ ✓ 已同步 %d 个文件到仓库副本" % (len(added) + len(changed)))
    if removed:
        print("  ⚠️ 下列文件在源里已删、副本里仍留着（本脚本不自动删，请手动 git rm）：")
        for r in removed:
            print("     %s" % r)
    print("  下一步: cd %s && git status" % REPO_ROOT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
