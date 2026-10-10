# -*- coding: utf-8 -*-
"""一次性手术：把 report_build_v31.m29() 换成「只调 build/score_lock.py」的薄壳。

【为什么】
  槽 29 此前由本函数自己拼十项表 + 自己算分，于是每做一家就重写一次，
  线上留下三种形态。用户 2026-09-22 指令「企业评分的模块锁死，不要每次都改」
  ⇒ 把结构与文案搬到 score_lock.py（唯一真源），m29 退化成数据入口。

【做法】按 `def m29(d):` … `def m30(d):` 之间的整块替换（不靠人工数行号），
  并在 import 区补 `import score_lock as SL`。

自检（缺一即停）：
  ① 替换前必须恰好命中 1 个 m29 块、1 处 import 锚点
  ② 替换后 m29 正文里不得再有 `table(` / `FULL =` / `sc(`（旧规则残留）
  ③ py_compile 通过
  ④ 备份原文件到 backup/report_build_v31_<ts>.py

用法：
    python _rewire_m29.py          # 干跑，只报告
    python _rewire_m29.py --go     # 落盘 + 编译
"""
import io
import os
import py_compile
import re
import shutil
import sys
import time

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, 'report_build_v31.py')
BAK = os.path.join(HERE, 'backup')

NEW_M29 = '''def m29(d):
    """29 企业评分（选股原则 10 项 · 满分 100）

    ★★★ 本模块**已锁死**（2026-09-22 用户指令：「企业评分的模块锁死，不要每次都改」）。
        模块结构与文案的唯一真源 = ``build/score_lock.py``；本函数只负责把数据喂进去。
        **禁止**在这里重新拼表格、改项名 / 权重、或另起一套评分规则。
        数据侧只认 ``score.kpi``（KPI 卡 8 格）/ ``score.h1``（报告期三格）/
        ``score.date`` / ``score.period`` / ``score.notes``（逐项实测说明，可选）。
        ⚠️ 历史遗留的 ``score.items`` 覆写口子**已作废** —— 那正是「每次都改」的成因；
        数据里出现即告警（不报错，避免打断别人的构建）。
    """
    sc = g(d, 'score', default={}) or {}
    if sc.get('items'):
        sys.stderr.write(
            '[score-lock] 告警：%s 仍带 score.items（已作废、被忽略）。'
            '槽 29 已锁死，项名与权重只能来自 build/score_lock.py。\\n' % d.get('code'))
    fin = g(d, 'fin', default={}) or {}
    kpi = SL.kpi_from_fin(fin, sc)
    out = [SL.render(kpi=kpi, period=sc.get('period') or '', notes=sc.get('notes'))]
    out += deep(d, 'score')
    return '\\n    '.join(out)


'''


def main(go):
    src = io.open(SRC, encoding='utf-8').read()
    problems = []

    # ① 定位 m29 块
    m_start = re.search(r'^def m29\(d\):\n', src, re.M)
    m_end = re.search(r'^def m30\(d\):\n', src, re.M)
    if not m_start or not m_end or m_end.start() <= m_start.start():
        problems.append('未命中 m29 → m30 区块')
    n_m29 = len(re.findall(r'^def m29\(d\):', src, re.M))
    if n_m29 != 1:
        problems.append('m29 定义出现 %d 次（应为 1）' % n_m29)

    # ② 定位 import 锚点
    anchor = 'import chartmap                       # 储量地图工具（build/chartmap.py）'
    n_anchor = src.count(anchor)
    if n_anchor != 1:
        problems.append('import 锚点出现 %d 次（应为 1）' % n_anchor)
    if 'import score_lock' in src:
        problems.append('已存在 import score_lock（疑似重复执行）')

    if problems:
        print('中止：')
        for p in problems:
            print('  ✗', p)
        return 1

    old_block = src[m_start.start():m_end.start()]
    print('待替换区块：%d 字节 / %d 行' % (len(old_block.encode('utf-8')),
                                          old_block.count('\n')))
    print('旧块含 table( : %s | FULL = : %s | sc( : %s'
          % ('table(' in old_block, 'FULL =' in old_block, 'sc(' in old_block))

    new_src = (src[:m_start.start()] + NEW_M29 + src[m_end.start():])
    new_src = new_src.replace(anchor, anchor + '\nimport score_lock as SL                 # ★ 槽 29 冻结模块（唯一真源）', 1)

    # ③ 新 m29 正文不得残留旧规则
    blk = new_src[new_src.index('def m29(d):'):new_src.index('def m30(d):')]
    for bad in ('table(', 'FULL =', 'sc(roe', 'sc(gm', 'ov = {'):
        if bad in blk:
            print('中止：新 m29 正文仍含旧规则残留 %r' % bad)
            return 1
    if 'SL.render(' not in blk:
        print('中止：新 m29 未调用 score_lock')
        return 1

    print('新块：%d 字节' % len(blk.encode('utf-8')))
    if not go:
        print('\n干跑结束（未落盘）。加 --go 落盘。')
        return 0

    os.makedirs(BAK, exist_ok=True)
    dst = os.path.join(BAK, 'report_build_v31_%s.py' % time.strftime('%Y%m%d_%H%M%S'))
    shutil.copy2(SRC, dst)
    io.open(SRC, 'w', encoding='utf-8').write(new_src)
    print('已备份 → %s' % dst)
    print('已落盘 %s（%d 字节）' % (SRC, len(new_src.encode('utf-8'))))

    py_compile.compile(SRC, doraise=True)
    print('py_compile 通过 ✅')
    return 0


if __name__ == '__main__':
    sys.exit(main('--go' in sys.argv))
