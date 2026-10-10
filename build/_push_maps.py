# -*- coding: utf-8 -*-
"""把「储量地图」这一轮的改动落到线上库（只动两家、只动必要行）：

  A. `wb_report_mods`：槽 25 的 html（600459 / 002237）—— 只 PATCH 这两行，
     绝不重跑 `push_reports_v31.py`（那会把另 30 行无谓重写，且工作区可能被并发会话共享）。
  B. `wb_report_charts`：新增 4 行地图 option（id = `<code>_<slot>`，走 on_conflict=id upsert）。

守卫（与 `_blank29.py` / `_ds_apply.py` 同一套，四件都不能省）：
  ① **漂移闸**：写模块前先读线上槽 25，必须逐字节等于**本地 seed 的旧值**；
     不等说明线上被网页端编辑过 ⇒ 拒绝覆盖并停手。
  ② **备份**：把线上旧模块 html 与将新增的图行整体快照到 build/backup/。
  ③ **幂等**：线上已是新值 ⇒ 跳过（可反复跑）。
  ④ **回读**：写完重读，模块按字符串比、图表按**解析后的 dict** 比
     （jsonb 往返会重排键序，比 md5 必假红）。

用法：python build/_push_maps.py            # 干跑
      python build/_push_maps.py --go       # 写库
      python build/_push_maps.py --go --sync-seed   # 写库并同步本地 seed
"""
import io
import json
import os
import sys
import time
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import report_build_v31 as B                                     # noqa: E402

GO = '--go' in sys.argv
SYNC = '--sync-seed' in sys.argv
# ★★★ 临时降级开关（2026-09-21）：地图 tooltip 的令牌需要**参数化后的壳**才能解析。
#   托管侧的登录态当前失效（`auth(status)` 回 auth_status=REQUIRED），上传不了壳；
#   而旧壳的 mapCnTip 会把 `铂族金属资源储量~吨~…` 整段当单位拼进 tooltip
#   ⇒ 直接推真令牌会**在页面上漏出令牌串**。
#   所以带 `--safe-tooltip` 时把 tooltip 关掉（数值本来就已经标注在图上、
#   并且完整列在紧随其后的分省表里）—— 保证线上不留缺陷；
#   等壳上传成功后，**不加这个开关再跑一次**即可恢复带 tooltip 的正式形态。
SAFE_TIP = '--safe-tooltip' in sys.argv
CFG = json.load(io.open(os.path.join(HERE, 'cloud.json'), encoding='utf-8'))
BASE = 'https://%s.api.tcloudbasegateway.com/v1/rdb/rest/' % CFG['envId']
HDR = {'apikey': CFG['key'], 'Authorization': 'Bearer ' + CFG['key'],
       'Accept': 'application/json', 'Content-Type': 'application/json'}


def req(path, method='GET', body=None, tries=8):
    last = None
    for i in range(tries):
        try:
            data = json.dumps(body, ensure_ascii=False).encode('utf-8') if body is not None else None
            rq = urllib.request.Request(BASE + path, data=data, headers=HDR, method=method)
            with urllib.request.urlopen(rq, timeout=120) as r:
                raw = r.read().decode('utf-8')
            return json.loads(raw) if raw.strip() else None
        except urllib.error.HTTPError as e:
            if 400 <= e.code < 500:
                raise SystemExit('✗ HTTP %s（%s）%s' % (e.code, path[:70], e.read()[:300]))
            last = e
        except Exception as e:                                    # noqa: BLE001
            last = e
        print('      · 重试 %d/%d %s' % (i + 1, tries, type(last).__name__))
        time.sleep(3 * (i + 1))
    raise SystemExit('✗ 连续失败：%s' % last)


def dkey(o):
    return json.dumps(o, ensure_ascii=False, sort_keys=True)


LOGS = []


def say(s):
    LOGS.append(s)
    print(s)


def main():
    now = int(time.time() * 1000)
    plan = []
    for code in ('600459', '002237'):
        d = json.load(io.open(os.path.join(HERE, 'seed', 'data_v31_%s.json' % code),
                              encoding='utf-8'))
        new_html = B.m_res(d)
        maps = B.res_map_charts(d)
        if SAFE_TIP:
            maps = {k: _safe(v) for k, v in maps.items()}
        # 图行在库里的可读名（抽屉里显示的那种）—— 取数据块自己的 title
        names = {}
        for blk in ('world_map', 'cn_map'):
            mm = (d.get('resource') or {}).get(blk) or {}
            if mm.get('slot'):
                names[mm['slot']] = mm.get('title') or mm['slot']
        plan.append({'code': code, 'html': new_html, 'maps': maps, 'names': names})

    # ── 读线上现状 ────────────────────────────────────────────
    say('=' * 96)
    say('储量地图落库：600459 / 002237')
    say('=' * 96)
    snap = {'at': now, 'mods': {}, 'charts': {}}
    for p in plan:
        code = p['code']
        lm = req('wb_report_mods?report_id=eq.%s&no=eq.25&select=id,no,html,up' % code) or []
        if not lm:
            raise SystemExit('✗ %s 线上没有槽 25' % code)
        p['live_mod'] = lm[0]
        loc = json.load(io.open(os.path.join(HERE, 'seed', 'report_%s.json' % code),
                                encoding='utf-8'))
        old = next((m.get('html') or '' for m in loc['mods'] if str(m.get('no')) == '25'), '')
        p['local_old'] = old
        lv_html = p['live_mod'].get('html') or ''
        # ① 漂移闸
        if lv_html.strip() == p['html'].strip():
            p['mod_state'] = 'done'
        elif lv_html.strip() == old.strip():
            p['mod_state'] = 'todo'
        else:
            p['mod_state'] = 'drift'
        say('[%s] 槽25：线上 %d 字 / 本地旧值 %d 字 / 新值 %d 字 ⇒ %s'
            % (code, len(lv_html), len(old), len(p['html']),
               {'done': '线上已是新值（跳过）', 'todo': '待写入',
                'drift': '★ 漂移，拒绝覆盖'}[p['mod_state']]))
        lc = req('wb_report_charts?report_id=eq.%s&select=id,name,seq,opt&order=seq.asc'
                 % code) or []
        p['live_charts'] = lc
        p['maxseq'] = max([int(c.get('seq') or 0) for c in lc] or [0])
        by_key = {}
        for c in lc:
            cid = c['id']
            by_key[cid[len(code) + 1:] if cid.startswith(code + '_') else cid] = c
        p['by_key'] = by_key
        # ★ 必须用 p['maps'] —— 早先这里写成 sorted(maps)，`maps` 是上一个循环的
        #   残留变量（= 002237 的图）⇒ 干跑把 600459 的图槽名错报成 chartAu*
        for k in sorted(p['maps']):
            cur = by_key.get(k)
            same = bool(cur) and dkey(_opt(cur['opt'])) == dkey(p['maps'][k])
            say('       图 %-18s %s' % (k, '线上已一致（跳过）' if same else
                                     ('线上存在但内容不同（改写）' if cur else '线上不存在（新增）')))
            p.setdefault('chart_state', {})[k] = 'same' if same else ('patch' if cur else 'insert')
        if p['mod_state'] != 'drift':
            snap['mods'][code] = {'id': p['live_mod'].get('id'), 'no': 25, 'html': p['live_mod'].get('html')}
        snap['charts'][code] = {c['id']: c for c in lc}
        say('')

    if any(p['mod_state'] == 'drift' for p in plan):
        raise SystemExit('✗ 有公司出现漂移，已停手（先人工确认线上是否被网页端编辑）')

    if not GO:
        say('（干跑结束，未写库。加 --go 生效）')
        io.open(os.path.join(HERE, '_o_push_maps.txt'), 'w', encoding='utf-8').write('\n'.join(LOGS))
        return

    # ② 备份
    bk = os.path.join(HERE, 'backup', 'maps_pre_%s.json' % time.strftime('%Y%m%d-%H%M%S'))
    io.open(bk, 'w', encoding='utf-8').write(json.dumps(snap, ensure_ascii=False))
    say('快照 → %s（%.1f KB）' % (os.path.basename(bk), os.path.getsize(bk) / 1024.0))
    say('')

    # ── 写 ───────────────────────────────────────────────────
    for p in plan:
        code = p['code']
        if p['mod_state'] == 'todo':
            req('wb_report_mods?id=eq.%s' % p['live_mod']['id'], 'PATCH',
                {'html': p['html'], 'up': now})
            say('  ✔ PATCH 槽25 %s' % code)
        for k, st in p['chart_state'].items():
            if st == 'same':
                continue
            body = [{'id': '%s_%s' % (code, k), 'report_id': code, 'code': code,
                     'seq': p['maxseq'] + (1 if k.endswith('WorldMap') else 2),
                     'name': p['names'].get(k) or k, 'opt': p['maps'][k], 'up': now}]
            req('wb_report_charts?on_conflict=id', 'POST', body)
            say('  ✔ %s %s' % ('新增' if st == 'insert' else '改写', '%s_%s' % (code, k)))

    # ④ 回读
    time.sleep(1.2)
    say('')
    say('=== 回读复核（模块比字符串 / 图表比解析后的 dict —— jsonb 会重排键序）===')
    bad = 0
    for p in plan:
        code = p['code']
        lm = req('wb_report_mods?report_id=eq.%s&no=eq.25&select=html,up' % code)[0]
        ok = (lm.get('html') or '').strip() == p['html'].strip()
        bad += 0 if ok else 1
        say('  槽25 %-8s %s  up=%s' % (code, '逐字节一致 ✅' if ok else '★ 不一致 ❌', lm.get('up')))
        lc = {c['id']: c for c in (req('wb_report_charts?report_id=eq.%s&select=id,opt,up'
                                       % code) or [])}
        for k in sorted(p['maps']):
            got = lc.get('%s_%s' % (code, k))
            same = bool(got) and dkey(_opt(got['opt'])) == dkey(p['maps'][k])
            bad += 0 if same else 1
            say('  图 %s_%-18s %s  up=%s' % (code, k, '逐字段一致 ✅' if same else '★ 不一致 ❌',
                                              (got or {}).get('up')))

    # ③ 顺手把本地 seed 同步成线上值（下次干跑才不会误判「待写入」）
    if SYNC:
        for p in plan:
            f = os.path.join(HERE, 'seed', 'report_%s.json' % p['code'])
            s = json.load(io.open(f, encoding='utf-8'))
            for m in s['mods']:
                if str(m.get('no')) == '25':
                    m['html'] = p['html']
            by = {}
            for c in s['charts']:
                cid = c['id']
                by[cid[len(p['code']) + 1:] if cid.startswith(p['code'] + '_') else cid] = c
            for k, v in p['maps'].items():
                by[k] = {'id': '%s_%s' % (p['code'], k), 'name': k, 'opt': v}
            s['charts'] = list(by.values())
            io.open(f, 'w', encoding='utf-8').write(json.dumps(s, ensure_ascii=False, indent=1))
            say('  ✓ 本地 seed 已同步 %s' % f)
    say('')
    say('总判定：%s' % ('✅ 全部落地' if not bad else '❌ 有 %d 处未落地' % bad))
    io.open(os.path.join(HERE, '_o_push_maps.txt'), 'w', encoding='utf-8').write('\n'.join(LOGS))


def _opt(o):
    return json.loads(o) if isinstance(o, str) else o


def _safe(opt):
    """把地图 opt 的 tooltip 降级成「不显示」——**只在壳未升级时使用**（见 SAFE_TIP 注释）。

    为什么是 show:false 而不是换一段静态文案：世界底图里区域名是英文，
    `{b}` 会显示成「South Africa」；而 `{c}` 在 map series 上取不到 value
    （会画出字面量 NaN，作者已踩过）。既然图上标签与下方表格都已给全数值，
    干净地关掉悬浮，比给一段半对半错的文案更诚实。
    """
    o = json.loads(json.dumps(opt, ensure_ascii=False))   # 深拷贝，别改原对象
    o['tooltip'] = {'show': False}
    return o


if __name__ == '__main__':
    main()
