# -*- coding: utf-8 -*-
"""读 `_ds_new/` 里算好的新值 → 漂移闸 → PATCH 线上 → 写本地 seed/data → 回读。

★ 为什么与 `_drop_sens.py` 拆成两个文件：
  本环境出网**间歇性不可用**（实测：同一段代码同一秒跑，一次 SSL UNEXPECTED_EOF、
  一次 HTTP 200；有一次连续 8 次重试跨 84 秒全败，隔一分钟又全通）。
  已用 A/B 对照排除代码因素（独立小脚本 / import 模块 / 读大 JSON / 渲染 —— 均与联网成败无关）。
  ⇒ 把「耗时的渲染计算」与「联网写库」分开：算一次落盘，写库阶段只做 REST，
    失败重跑成本从约 1 分钟降到约 2 秒。本文件**不 import 任何渲染器**。

★ 可重复执行：每个槽三态判定 —— 线上 == 新值 ⇒ 已应用（跳过）；
  线上 == 本地旧值 ⇒ 待应用；其它 ⇒ 漂移，拒绝覆盖。

用法：
    python _drop_sens.py --dump      # ① 算好落盘（不联网）
    python _ds_apply.py              # ② 写库（联网，可反复跑）
"""
import hashlib
import io
import json
import os
import shutil
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
HERE = os.path.dirname(os.path.abspath(__file__))
SEED = os.path.join(HERE, 'seed')
BAK = os.path.join(HERE, 'backup')
DUMP = os.path.join(HERE, '_ds_new')
CFG = json.load(io.open(os.path.join(HERE, 'cloud.json'), encoding='utf-8'))
BASE = 'https://%s.api.tcloudbasegateway.com/v1/rdb/rest/' % CFG['envId']


def req(path, method='GET', body=None, tries=8):
    """REST 调用，带重试退避（窗口 ≈ 3+6+…+24 = 108 秒）。PATCH 幂等，重试安全。"""
    data = json.dumps(body, ensure_ascii=False).encode('utf-8') if body is not None else None
    hdr = {'apikey': CFG['key'], 'Authorization': 'Bearer ' + CFG['key'],
           'Accept': 'application/json', 'Content-Type': 'application/json'}
    last = None
    for i in range(tries):
        try:
            rq = urllib.request.Request(BASE + path, data=data, headers=hdr, method=method)
            with urllib.request.urlopen(rq, timeout=120) as r:
                raw = r.read().decode('utf-8')
            return json.loads(raw) if raw.strip() else None
        except Exception as e:                                   # noqa: BLE001
            last = e
            wait = 3 * (i + 1)
            print('      · 请求失败（第 %d/%d 次）%s —— %ds 后重试'
                  % (i + 1, tries, type(e).__name__, wait))
            time.sleep(wait)
    raise SystemExit('✗ REST 连续 %d 次失败，放弃：%s' % (tries, last))


def main():
    if not os.path.isdir(DUMP):
        print('✗ 没有 %s —— 先跑 python _drop_sens.py --dump' % DUMP)
        return 1
    files = sorted(f for f in os.listdir(DUMP) if f.endswith('.json'))
    if not files:
        print('✗ %s 为空 —— 先跑 python _drop_sens.py --dump' % DUMP)
        return 1

    ts = time.strftime('%Y%m%d-%H%M%S')
    print('=' * 96)
    print('写入线上 · %d 家 · 备份戳 %s' % (len(files), ts))
    print('=' * 96)

    # ── 三态漂移闸：逐槽先 GET，判定「待应用 / 已应用 / 漂移」 ──
    print('── 漂移闸 ──')
    todo, done, drift = {}, {}, []
    for f in files:
        b = json.load(io.open(os.path.join(DUMP, f), encoding='utf-8'))
        code = b['code']
        oldmap = {str(m['no']): (m['html'] or '') for m in b['seed_old_mods']}
        todo[code] = {}
        for no in sorted(b['mods'], key=lambda x: int(x)):
            live = req('wb_report_mods?select=html,up&report_id=eq.%s&no=eq.%s' % (code, no))
            lh = (live[0].get('html') or '') if live else ''
            if lh == b['mods'][no]:
                done.setdefault(code, []).append(no)
                print('   %s 槽%-3s 线上已是新值 ⇒ 跳过（幂等）' % (code, no))
            elif lh == oldmap[no]:
                todo[code][no] = b['mods'][no]
                print('   %s 槽%-3s 线上 == 本地旧值（%d 字符）⇒ 待写 · up=%s'
                      % (code, no, len(lh), live[0].get('up') if live else '?'))
            else:
                drift.append('%s 槽%s（线上 %d 字 / 旧值 %d 字 / 新值 %d 字）'
                             % (code, no, len(lh), len(oldmap[no]), len(b['mods'][no])))
                print('   %s 槽%-3s ❌ 漂移' % (code, no))
    if drift:
        print('   ✗ 检测到漂移，拒绝覆盖（需人工看一眼）：')
        for d in drift:
            print('      - %s' % d)
        return 1
    if not any(todo.values()):
        print('   ✓ 全部槽都已是新值，无需写入')
        return 0

    # ── 写入 ──
    os.makedirs(BAK, exist_ok=True)
    for f in files:
        b = json.load(io.open(os.path.join(DUMP, f), encoding='utf-8'))
        code = b['code']
        if not todo.get(code):
            continue
        seed_p = os.path.join(SEED, 'report_%s.json' % code)
        data_p = os.path.join(SEED, 'data_v31_%s.json' % code)
        for p in (seed_p, data_p):
            shutil.copy2(p, os.path.join(
                BAK, '%s_pre_dropsens_%s.json' % (os.path.basename(p)[:-5], ts)))
        print()
        print('【%s】' % code)
        for no in sorted(todo[code], key=lambda x: int(x)):
            r = req('wb_report_mods?report_id=eq.%s&no=eq.%s' % (code, no), 'PATCH',
                    {'html': todo[code][no], 'up': int(time.time() * 1000)})
            print('   PATCH 槽%-3s → 影响 %d 行'
                  % (no, len(r) if isinstance(r, list) else -1))
        io.open(seed_p, 'w', encoding='utf-8').write(
            json.dumps(b['seed'], ensure_ascii=False))
        io.open(data_p, 'w', encoding='utf-8').write(
            json.dumps(b['data'], ensure_ascii=False))
        ok = True
        for no in sorted(todo[code], key=lambda x: int(x)):
            back = req('wb_report_mods?select=html&report_id=eq.%s&no=eq.%s' % (code, no))
            same = (back[0].get('html') or '') == todo[code][no]
            ok = ok and same
            print('   回读槽%-3s：线上 == 新值 → %s' % (no, '✓' if same else '✗'))
        print('   本地已写 · md5 seed=%s data=%s'
              % (hashlib.md5(io.open(seed_p, 'rb').read()).hexdigest()[:10],
                 hashlib.md5(io.open(data_p, 'rb').read()).hexdigest()[:10]))
        if not ok:
            print('   ✗ 回读不一致，停手')
            return 1
    print('=' * 96)
    print('完成')
    return 0


if __name__ == '__main__':
    sys.exit(main())
