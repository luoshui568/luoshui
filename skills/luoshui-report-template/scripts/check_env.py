#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""洛水研报模版 · 环境体检

装好 skill 后先跑这个，确认「变量 + 项目文件 + 运行时」都就位。

用法:
    python3 scripts/check_env.py
    python3 scripts/check_env.py --proj /path/to/luoshui
    python3 scripts/check_env.py --py /usr/bin/python3 --pyv .venv/bin/python --tcb tcb

取值优先级:  命令行参数  >  环境变量  >  SKILL.md「★ 环境配置」表  >  内置默认值。

退出码: 0 = 无 FAIL；1 = 有 FAIL。
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL_DIR = HERE.parent
SKILL_MD = SKILL_DIR / "SKILL.md"

VARS = ("PROJ", "PY", "PYV", "TCB", "ENVID", "DOM")

# 写研报必需 / 建议有的文件（相对 PROJ）
REQUIRED = [
    ("build/report_template_v31.py", "蓝图（31 模块 / 十节唯一真源）"),
    ("build/report_build_v31.py", "渲染器"),
    ("build/push_reports_v31.py", "写库"),
    ("build/batch_assemble.py", "取数组装"),
    ("build/cloud.json", "CloudBase 凭据（envId + key）"),
    ("build/seed", "种子数据目录"),
    ("deploy/report.template.html", "研报页模板"),
    ("deliver", "交付目录"),
]
OPTIONAL = [
    ("build/block_style.css", "表格配色样式源"),
    ("build/block_style.js", "表格装饰脚本源"),
    ("build/make_font_css.py", "阿里普惠体子集生成器"),
    ("build/block_font.css", "内嵌字体 CSS（派生物）"),
    ("build/lib/world-cn.js", "国标世界地图底图"),
    ("build/probe_report_mac.py", "线上真字节探针（mac）"),
    ("build/check_map_compliance.py", "地图合规自检"),
]

FAILS, WARNS = [], []


def mark(ok):
    return {True: "\u2713", False: "\u2717", None: "\u00b7"}[ok]


def line(ok, label, detail="", warn=False):
    """ok=True 通过 / False 失败 / None 提示。warn=True 时 False 记 WARN 而不是 FAIL。"""
    print("  %s %-34s %s" % (mark(ok), label, detail))
    if ok is False:
        (WARNS if warn else FAILS).append(label)
    return ok


def run(cmd, timeout=25):
    """跑一条命令，返回 (returncode, 合并输出)。命令不存在时返回 (None, msg)。"""
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except FileNotFoundError:
        return None, "命令不存在"
    except subprocess.TimeoutExpired:
        return -1, "超时"
    except Exception as e:                                   # noqa: BLE001
        return -1, str(e)


def parse_config_from_skill():
    """从 SKILL.md 的「★ 环境配置」表里读出变量值（容忍格式微调）。"""
    out = {}
    if not SKILL_MD.exists():
        return out
    try:
        text = SKILL_MD.read_text(encoding="utf-8")
    except Exception:                                        # noqa: BLE001
        return out
    for raw in text.splitlines():
        row = raw.strip()
        if not row.startswith("|"):
            continue
        cells = [c.strip() for c in row.strip("|").split("|")]
        if len(cells) < 3:
            continue
        keys = [k for k in re.findall(r"`([A-Z]+)`", cells[0]) if k in VARS]
        vals = re.findall(r"`([^`]+)`", cells[2])
        if not keys or not vals:
            continue
        if len(keys) == len(vals):
            for k, v in zip(keys, vals):
                out.setdefault(k, v)
        elif len(vals) == 1:
            out.setdefault(keys[0], vals[0])
    return out


def resolve(overrides):
    """合并四层取值来源。"""
    cfg = {
        "PROJ": "/Users/luoshui/WorkBuddy/2026-10-10-22-59-27/luoshui",
        "PY": "/Users/luoshui/.workbuddy/binaries/python/envs/default/bin/python",
        "PYV": "/Users/luoshui/.workbuddy/binaries/python/envs/default/bin/python",
        "TCB": "/Users/luoshui/.workbuddy/binaries/node/cli-connector-packages/bin/tcb",
        "ENVID": "fdels568-d7g1d8o3y90a80cd7",
        "DOM": "liuchaowang.cn",
    }
    cfg.update(parse_config_from_skill())                    # 3) SKILL.md
    for k in VARS:                                           # 2) 环境变量
        if os.environ.get(k):
            cfg[k] = os.environ[k]
    for k, v in overrides.items():                           # 1) 命令行
        if v:
            cfg[k] = v
    return cfg


def expand(p, cfg):
    """把 $PROJ / $PY / ~ 展开成实际路径。"""
    if not p:
        return p
    p = os.path.expanduser(p)
    for k in VARS:
        p = p.replace("$" + k, cfg.get(k, ""))
    return p


def main():
    ap = argparse.ArgumentParser(description="洛水研报模版 · 环境体检")
    for k in VARS:
        ap.add_argument("--" + k.lower(), dest=k, default=None,
                        help="覆盖 %s（默认读 SKILL.md 的 ★ 环境配置）" % k)
    args = ap.parse_args()
    cfg = resolve({k: getattr(args, k) for k in VARS})

    print("=" * 66)
    print("洛水研报模版 · 环境体检")
    print("skill 目录 : %s" % SKILL_DIR)
    print("=" * 66)

    # ── 1. 配置值
    print("\n[1/4] 配置值（改 SKILL.md 的「★ 环境配置」或命令行传参）")
    for k in VARS:
        src = ""
        env_from_skill = parse_config_from_skill().get(k)
        if getattr(args, k):
            src = " ← 命令行"
        elif os.environ.get(k):
            src = " ← 环境变量"
        elif env_from_skill:
            src = " ← SKILL.md"
        else:
            src = " ← 内置默认"
        print("  %-6s %-58s%s" % (k, cfg[k], src))
    if not SKILL_MD.exists():
        line(False, "SKILL.md 存在", "找不到 %s" % SKILL_MD)

    # ── 2. 运行时
    print("\n[2/4] 运行时")
    py = expand(cfg["PY"], cfg)
    rc, out = run([py, "-c", "import sys;print('%d.%d.%d' % sys.version_info[:3])"])
    if rc == 0 and out.strip():
        ver = out.strip().splitlines()[0] if out.strip() else "?"
        major = int(ver.split(".")[0]); minor = int(ver.split(".")[1])
        ok_ver = major > 3 or (major == 3 and minor >= 9)
        line(ok_ver, "PY 可执行", "Python %s%s" % (ver, "" if ok_ver else "  ← 需要 3.9+"))
    elif os.path.isfile(py) and os.path.getsize(py) == 0:
        # ★ 作者本机真实踩过：managed 3.13 的 python3.13 被截成 0 字节，
        #   跑它 rc=0 但**一个字符都不输出** ⇒ 所有脚本"成功但没结果"。
        line(False, "PY 可执行",
             "%s 是 0 字节（二进制被截断）⇒ 改用 envs/default/bin/python" % py)
    elif rc == 0:
        line(False, "PY 可执行",
             "%s 跑通了但没有任何输出 —— 多半是二进制被截断，换 envs/default/bin/python" % py)
    else:
        line(False, "PY 可执行", "%s (%s)" % (py, out.strip()[:40]))

    pyv = expand(cfg["PYV"], cfg)
    rc, out = run([pyv, "-c", "import PIL;print(PIL.__version__)"])
    if rc == 0:
        line(True, "PYV 带 PIL", "pillow %s" % out.strip().splitlines()[0])
    else:
        line(False, "PYV 带 PIL", "截图 / 拼图类探针会不可用（%s）" % out.strip()[:40], warn=True)

    tcb = expand(cfg["TCB"], cfg)
    rc, out = run([tcb, "--version"])
    if rc == 0:
        line(True, "TCB 可执行", out.strip().splitlines()[0][:48])
    else:
        if shutil.which("tcb"):
            line(True, "TCB 可执行", "PATH 里有 tcb（SKILL.md 里的路径无效，用 PATH 的即可）")
        else:
            line(False, "TCB 可执行", "没找到 CloudBase CLI ⇒ 只影响「部署上线」", warn=True)

    node = shutil.which("node")
    if node:
        rc, out = run([node, "-v"])
        line(True, "node 在 PATH", "%s" % (out.strip() or node))
    else:
        line(False, "node 在 PATH", "缺 node ⇒ `node --check` 语法检查不可用", warn=True)

    # ── 3. 项目文件
    proj = Path(expand(cfg["PROJ"], cfg))
    print("\n[3/4] 项目根: %s" % proj)
    if not proj.is_dir():
        line(False, "项目根存在", "目录不存在 —— 先把仓库克隆下来，或用 --proj 指定")
    else:
        line(True, "项目根存在", "")
        miss = 0
        for rel, desc in REQUIRED:
            p = proj / rel
            ok = p.exists()
            if not ok:
                miss += 1
            line(ok, rel, desc if ok else "缺失 · %s" % desc)
        print("  ── 以下为建议项（缺了只影响部分环节）──")
        for rel, desc in OPTIONAL:
            p = proj / rel
            msg = desc if p.exists() else "缺失 · %s" % desc
            if not p.exists() and rel == "build/block_font.css":
                msg = "缺失 ⇒ 跑 $PY build/make_font_css.py --fetch（否则页面掉回系统字体）"
            line(p.exists(), rel, msg, warn=True)
        if miss:
            print("  ⇒ 缺 %d 个必需文件，仓库可能不完整" % miss)

    # ── 4. 结论
    print("\n[4/4] 结论")
    if FAILS:
        print("  \u2717 FAIL %d 项：" % len(FAILS))
        for f in FAILS:
            print("      - %s" % f)
    else:
        print("  \u2713 必需项全部通过")
    if WARNS:
        print("  \u00b7 WARN %d 项（不影响核心流程）：%s" % (len(WARNS), " / ".join(WARNS)))
    print()
    if FAILS:
        print("请先修掉 FAIL 项；改完重跑本脚本。详见 INSTALL.md §5 / §6。")
    else:
        print("环境就绪。现在可以对 AI 说：「用洛水研报模版帮我写一个 XX 的深度研究报告」。")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
