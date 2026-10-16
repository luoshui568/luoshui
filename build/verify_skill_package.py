#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""校验技能包能否被 WorkBuddy 导入（复刻客户端的三道校验）

WorkBuddy 上传技能时走 `uploadCustomSkill()`，它会做三件事
（以下规则取自 app.asar 里 `uploadCustomSkill` / `findSkillMdEntry` /
`assertSkillUploadFrontmatterValid` / `SkillMdFrontmatterError` 的实现）：

  ① 扩展名必须是 `.zip` / `.tar.gz` / `.tgz` / `.skill`
     → `n.name.replace(/\\.(zip|tar\\.gz|tgz|skill)$/i, '')`
  ② 包内必须能找到 SKILL.md（**根目录或任意子目录都行**）
     → `entryName.replace(/\\\\/g,'/')` 后测 `/(^|\\/)SKILL\\.md$/i`
  ③ SKILL.md 的 frontmatter 必须能被 YAML 解析
     → 先测 `/^---\\s*\\r?\\n([\\s\\S]*?)\\r?\\n---\\s*(?:\\r?\\n|$)/`
       再解析；失败抛 `SkillMdFrontmatterError`（值里出现「ASCII 冒号+空格」是常见雷）

用法:
    python3 build/verify_skill_package.py <包路径> [<包路径> ...]

退出码: 0 = 全部可导入；1 = 有包会被拒。
"""

import io
import os
import re
import sys
import tarfile
import zipfile

# ── 与客户端一致的三条规则 ────────────────────────────────
EXT_RE = re.compile(r"\.(zip|tar\.gz|tgz|skill)$", re.I)
SKILL_MD_RE = re.compile(r"(^|/)SKILL\.md$", re.I)
FRONTMATTER_RE = re.compile(r"^---\s*\r?\n([\s\S]*?)\r?\n---\s*(?:\r?\n|$)")

# 客户端里出现过的量级限制（10 MB / 100 MB），仅作提示
SOFT_LIMIT = 10 * 1024 * 1024

try:
    import yaml                     # 有就用真解析器
except Exception:                   # noqa: BLE001
    yaml = None


def mark(ok):
    return "\u2713" if ok else "\u2717"


def frontmatter_check(text):
    """返回 (ok, 说明)。复刻客户端的正则 + YAML 解析。"""
    m = FRONTMATTER_RE.match(text)
    if not m:
        return False, "找不到合法 frontmatter 块（需以 --- 开头并以 --- 收尾）"
    body = m.group(1)
    if yaml is not None:
        try:
            data = yaml.safe_load(body)
        except Exception as e:                       # noqa: BLE001
            return False, "YAML 解析失败：%s" % str(e).split("\n")[0][:110]
        if not isinstance(data, dict):
            return False, "frontmatter 不是键值对"
        if not str(data.get("name", "")).strip():
            return False, "frontmatter 缺 name"
        if not any(str(data.get(k, "")).strip()
                   for k in ("description", "description_zh", "description_en")):
            return False, "frontmatter 缺 description / description_zh / description_en"
        return True, "name=%s" % data["name"]
    # 没有 yaml 库时的降级检查：找「ASCII 冒号 + 空格」这种 YAML 雷
    bad = []
    for ln in body.split("\n"):
        if ":" not in ln:
            continue
        val = ln.split(":", 1)[1]
        if re.search(r":\s", val):
            bad.append(ln)
    if bad:
        return False, "疑似 YAML 冲突（值里含「冒号+空格」）：%s" % bad[0][:60]
    if "name:" not in body:
        return False, "frontmatter 缺 name"
    if "description" not in body:
        return False, "frontmatter 缺 description"
    return True, "（未装 PyYAML，做了降级检查）"


def check_zip(path):
    with zipfile.ZipFile(path) as z:
        names = [n.replace("\\", "/") for n in z.namelist()]
        hit = [n for n in names if SKILL_MD_RE.search(n)]
        if not hit:
            return False, "包内找不到 SKILL.md", None
        raw = z.read([n for n in z.namelist()
                      if SKILL_MD_RE.search(n.replace("\\", "/"))][0])
    return True, hit[0], raw.decode("utf-8", "replace")


def check_tar(path):
    with tarfile.open(path) as t:
        names = [m.name.replace("\\", "/") for m in t.getmembers() if m.isfile()]
        hit = [n for n in names if SKILL_MD_RE.search(n)]
        if not hit:
            return False, "包内找不到 SKILL.md", None
        f = t.extractfile(hit[0])
        return True, hit[0], f.read().decode("utf-8", "replace")


def verify(path):
    print("=" * 68)
    print("校验:", path)
    if not os.path.isfile(path):
        print("  %s 文件不存在" % mark(False))
        return False
    size = os.path.getsize(path)
    ok = True

    # ① 扩展名
    e1 = bool(EXT_RE.search(path))
    print("  %s ① 扩展名合法 (.zip/.tar.gz/.tgz/.skill)    %s"
          % (mark(e1), os.path.splitext(path)[1] or "(无)"))
    ok &= e1

    # ② SKILL.md 位置
    try:
        if path.lower().endswith(".zip") or path.lower().endswith(".skill"):
            found, where, text = check_zip(path)
        else:
            found, where, text = check_tar(path)
    except Exception as ex:                          # noqa: BLE001
        print("  %s ② 读取包失败：%s" % (mark(False), ex))
        return False
    print("  %s ② 包内找到 SKILL.md                        %s"
          % (mark(found), where if found else ""))
    ok &= found

    # ③ frontmatter
    if found:
        fm_ok, note = frontmatter_check(text)
        print("  %s ③ frontmatter 合法                        %s"
              % (mark(fm_ok), note))
        ok &= fm_ok
        # 头尾应当是 --- 收尾（客户端正则要求）
        print("  %s ④ frontmatter 以 --- 收尾                  %s"
              % (mark(FRONTMATTER_RE.match(text) is not None), ""))

    # 体积提示
    if size > SOFT_LIMIT:
        print("  \u00b7 体积 %.1f MB —— 客户端出现过 10 MB 量级限制，建议压缩"
              % (size / 1024 / 1024))
    else:
        print("  \u00b7 体积 %.0f KB（远低于限制）" % (size / 1024))

    print("  ⇒ %s" % ("可被 WorkBuddy 直接导入" if ok else "会被客户端拒绝，需修复"))
    return ok


def main():
    args = sys.argv[1:]
    if not args:
        d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "deliver")
        args = [os.path.join(d, "luoshui-report-template.zip"),
                os.path.join(d, "luoshui-report-template.skill")]
    print("规则来源: app.asar 的 uploadCustomSkill / findSkillMdEntry /"
          " assertSkillUploadFrontmatterValid")
    results = [verify(a) for a in args]
    print()
    print("=" * 68)
    print("结论：%d/%d 个包可导入%s"
          % (sum(results), len(results), "" if all(results)
             else "  ← 有包需要修复"))
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
