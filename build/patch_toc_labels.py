# -*- coding: utf-8 -*-
"""把 5 份研报的「目录文案」统一成干净版（去掉「第X篇」前缀 + 补回被截断的字）。

背景（2026-09-16）：侧栏目录原来只有 132px 宽，历史文案被 `title[:8]` 硬截断，
库里存的是「第四篇 公司营业收入与利」（少一个「润」字）。用户反馈
「不要显示前面第几篇，把主要的字挡住了」→ 侧栏加宽到 166px，文案改成纯模块名
（≤9 字），页面端另有 `tocLabel()` 兜底剥前缀。

⚠️ 只改 `report.toc` 一个字段，**不碰** mods / charts ——
   整份重推会抹掉网页端的在线改动（铁律）。
⚠️ 锚点（anchor）被认为可能是网页端手改过的，因此只换 text；锚点集合与模板
   不一致的行会被跳过并提示，不做自动对齐。

用法：
  python build/patch_toc_labels.py             # 干跑：只打印差异
  python build/patch_toc_labels.py --apply     # 写种子 + PATCH 云端 wb_reports
"""
import io
import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SEED = os.path.join(HERE, 'seed')
sys.path.insert(0, HERE)
from report_template_v31 import new_toc  # noqa: E402

CFG = json.load(io.open(os.path.join(HERE, 'cloud.json'), encoding='utf-8'))
REST = 'https://%s.api.tcloudbasegateway.com/v1/rdb/rest/' % CFG['envId']
# ⚠️⚠️ **600456 已被刻意排除**（2026-09-20）：它现在是**十段目录 / 31 模块**
#      （投资核心·公司简介·公司业务·公司营收·公司投资·公司链条·行业分析·供需分析·
#       盈利预测·企业评分），与本文件 WANT（模板六篇）根本不是一套结构。
#      留着它 = 一跑就把十段目录刷回六段、且因锚点对不上直接 abort。
#      重排用 build/restructure_600456.py，别再往这里加 600456。
CODES = ['000731', '000830', '002237', '600459']
WANT = [dict(x) for x in new_toc()]
WANT_TEXTS = [x['text'] for x in WANT]
WANT_ANCHORS = [x['anchor'] for x in WANT]


def req(url, method='GET', body=None):
    h = {'Authorization': 'Bearer ' + CFG['key'], 'Content-Type': 'application/json'}
    r = urllib.request.Request(url, method=method, headers=h)
    if body is not None:
        r.data = json.dumps(body).encode('utf-8')   # ⚠️ 是 data= 不是 body=，Request 没有 body 参数
    with urllib.request.urlopen(r, timeout=90) as f:
        t = f.read().decode('utf-8')
    return json.loads(t) if t.strip() else None


def live_rows():
    q = "wb_reports?select=id,code,toc&id=in.(%s)" % ','.join(CODES)
    return {r['id']: r for r in (req(REST + q) or [])}


def seed_toc(code):
    d = json.load(io.open(os.path.join(SEED, 'report_%s.json' % code), encoding='utf-8'))
    return d, [x.get('text') for x in (d['report'].get('toc') or [])]


def main():
    apply_it = '--apply' in sys.argv
    live = live_rows()
    print('线上命中 %d / %d 行' % (len(live), len(CODES)))
    skip = []
    for code in CODES:
        cur = live.get(code, {}).get('toc') or []
        anchors = [x.get('anchor') for x in cur]
        texts = [x.get('text') for x in cur]
        _, stexts = seed_toc(code)
        print('\n[%s] %s' % (code, (live.get(code) or {}).get('code', '')))
        print('   线上旧: %s' % ' / '.join(str(t) for t in texts))
        print('   本地旧: %s' % ' / '.join(str(t) for t in stexts))
        print('   新    : %s' % ' / '.join(WANT_TEXTS))
        if anchors != WANT_ANCHORS:
            skip.append(code)
            print('   ⚠️ 锚点与模板不一致（网页端改过？）→ 跳过，请人工确认')

    if not apply_it:
        print('\n（干跑结束，加 --apply 才真正写）')
        return

    print('\n----- 开始写入 -----')
    for code in CODES:
        if code in skip:
            print('[%s] 跳过（锚点漂移）' % code)
            continue
        d, _ = seed_toc(code)
        # 只换 text，锚点原样保留
        d['report']['toc'] = [dict(x) for x in WANT]
        p = os.path.join(SEED, 'report_%s.json' % code)
        io.open(p, 'w', encoding='utf-8').write(json.dumps(d, ensure_ascii=False, indent=1))
        req(REST + 'wb_reports?id=eq.%s' % code, 'PATCH', {'toc': [dict(x) for x in WANT]})
        print('[%s] 种子 + 云端 toc 已更新' % code)

    back = live_rows()
    bad = []
    for code in CODES:
        got = [x.get('text') for x in (back.get(code, {}).get('toc') or [])]
        if got != WANT_TEXTS:
            bad.append((code, got))
    print('\n复核：5 行 toc == 期望 → %s' % (not bad))
    for code in CODES:
        print('  ', code, [x.get('text') for x in (back.get(code, {}).get('toc') or [])])
    if bad:
        print('❌ 未对齐：%s' % bad)
        sys.exit(1)


if __name__ == '__main__':
    main()
