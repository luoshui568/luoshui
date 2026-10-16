# -*- coding: utf-8 -*-
"""把各研报「核心结论」里的建档 / 口径 / 评级注解拆到 wb_reports.notice_html。

用户口径（2026-10-14）：
  「研报的核心结论重构一下，研报里不要有类似『本报告按 31 模块标准模板建档…』这种注解，
    可以在头部做一个点击弹窗显示，注解之类的全部归到一起。」

做法：
  · 逐篇用正则把注解**原文切出来**（一字不改地放进 notice_html，保证不丢信息），
    verdict_html 只留结论本身；
  · 002237 原结论删掉注解后只剩「公司身份 + 两个数字」，已不成结论 → 按报告自身
    m1/m10/m18/m27/m30/m31 的实测事实重写一版实质判断（见 NEW_VERDICT），
    不改任何数字，只是把散在正文里的判读结论提到前面。

幂等：
  · notice_html 已有值时不再覆盖；
  · verdict_html 里已找不到该注解时跳过（打印 ⚠️ 未命中，不算失败）。

用法：
  python3 patch_notice.py          # 写库
  python3 patch_notice.py --dry    # 只打印将要发生的改动
"""
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
HERE = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(io.open(os.path.join(HERE, 'cloud.json'), encoding='utf-8'))
REST = 'https://%s.api.tcloudbasegateway.com/v1/rdb/rest/' % CFG['envId']
HDR = {'Authorization': 'Bearer ' + CFG['key'], 'Content-Type': 'application/json',
       'Prefer': 'return=minimal'}

# 从 verdict_html 里切出去的注解（切出的原文原样进 notice_html）
STRIP = {
    '002237': [r'本报告按\s*31\s*模块标准模板建档：.*?不给出评级与目标价</strong>。'],
    '600459': [r'本报告按\s*31\s*模块标准模板建档：.*?不给出评级与目标价</strong>。'],
    '600392': [r'(?:\s*<br\s*/?>\s*)*本报告按\s*31\s*模块标准模板建档：.*?一律标注\s*\[模型输出\]。',
               r'\s*基于当前资料深度，<strong>本报告不给出评级与目标价</strong>，'
               r'仅给出可跟踪的触发条件与观测阈值。'],
    '601118': [r'\s*基于当前资料深度，<strong>不给出评级与目标价</strong>，'
               r'但给出明确的复核触发条件（见 M31）。'],
    '601958': [r'\s*基于当前资料深度，<strong>不给出评级与目标价</strong>，'
               r'但给出明确的复核触发条件（见 M31）。'],
    '603977': [r'\s*基于当前资料深度，<strong>不给出评级与目标价</strong>，'
               r'但给出明确的复核触发条件（见 M31）。'],
}

# 重写后的核心结论（只改叙述结构，数字全部取自该报告正文）
NEW_VERDICT = {
    '002237': (
        '<strong>恒邦股份（002237）</strong>是一家「通道型」贵金属冶炼企业 —— 江西铜业控股、'
        '江西省国资委实控，主营黄金冶炼（黄金 109.82 吨 / 白银 1,200 吨 / 电解铜 33.5 万吨产能）。'
        '2025 年营业收入 <strong>1,123.94 亿元</strong>（+48.28%）、归母净利 <strong>6.38 亿元</strong>'
        '（+18.80%），营收规模居可比四家之首，但<strong>毛利率仅 2.03%、净利率 0.55%</strong>。'
        '<strong>核心矛盾是：它的收入随金价放大，利润却由加工费决定。</strong>'
        '原料以外购金精矿为主（自产金备案储量仅 150.10 吨），金价上行只抬高收入基数、'
        '并把毛利率被动摊薄 —— 毛利率 2021 年 5.03% → 2025 年 2.03% 单调下行，'
        '所以「营收创新高」对恒邦几乎不含正面信息。<strong>护城河不可量化</strong>：'
        'ROIC 从 4.24% 降至 3.52%，连续五年低于 7.0% 的资本成本假设，'
        '本质是一家赚加工费的通道型企业。⚠️ <strong>2026 年的利润质量更需警惕</strong>：'
        'Q1 归母净利 1.82 亿元中含减持万国黄金一次性投资收益 3.45 亿元，剔除后主营实际亏损，'
        '同期计提存货跌价 6.24 亿元；2025 年经营现金流 −20.05 亿元、净现比 −3.14，'
        '资产负债率升至 64.00%。<strong>唯一能实质改变结论的变量是石坞金矿注入</strong>'
        '（承诺已超两年未交割）—— 它是把恒邦从「加工型」重估为「资源型」的唯一路径，'
        '同时改变资源禀赋与同业竞争。核心跟踪：石坞金矿交割进度、'
        '毛利率能否连续两期站稳 2.4% 以上、经营现金流与存货跌价。'
    ),
    '600459': (
        '<strong>贵研铂业（600459）</strong>是国内贵金属新材料领域不可替代的龙头'
        '（2025 年国内第一、全球第五，铂族金属回收市占率 30%+），但<strong>它的规模扩张长期靠垫资与加杠杆驱动</strong>：'
        '2025 年营业收入 <strong>556.75 亿元</strong>（+17.20%）、归母净利 <strong>6.41 亿元</strong>（+10.54%），'
        '营收是可比公司的 6~27 倍，毛利率却只有 <strong>2.63%</strong>（四家可比中最低）—— '
        '约七成收入来自「回收冶炼 + 供给服务」这类赚加工费或贸易价差的低毛利业务。'
        'ROIC 从 6.83%（2021）降至 5.45%（2025），<strong>连续五年低于 7.3% 的资本成本假设</strong>，'
        '技术领先尚未转化为定价权。2026H1 出现第一个反向信号：'
        '<strong>主动砍掉低毛利贸易后营收 −23.36%，归母净利反而 +7.63%、毛利率翻倍至 4.43%</strong>，'
        '且扣非增速（+12.75%）高于净利增速，说明改善来自主营结构而非一次性损益。'
        '因此当前的投资逻辑只有一条主线：<strong>以毛利率为唯一锚点，验证「技术领先能否转化为定价权」</strong>，'
        '需要连续两个报告期站稳 4%。核心跟踪：整体毛利率能否守住 4%、'
        '47 项贵研精品加工费同比（2026H1 +12.52%）、经营现金流（2026H1 +7.17 亿元）与财务费用增速（+149.23%）。'
    ),
}


def req(path, method='GET', body=None, timeout=120):
    data = json.dumps(body, ensure_ascii=False).encode('utf-8') if body is not None else None
    r = urllib.request.Request(REST + path, data=data, headers=HDR, method=method)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            raw = resp.read().decode('utf-8', 'replace')
            return resp.status, (json.loads(raw) if raw.strip() else None)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', 'replace')[:600]
    except Exception as e:
        return 0, str(e)


def plain(html):
    return re.sub(r'<[^>]+>', '', html or '')


def main():
    dry = '--dry' in sys.argv
    now = int(time.time() * 1000)
    codes = sorted(STRIP.keys())
    print('目标研报：%s%s' % ('、'.join(codes), '（--dry 只读不写）' if dry else ''))
    print('=' * 100)

    changed = 0
    for code in codes:
        st, rows = req('wb_reports?code=eq.%s&select=id,code,name,verdict_html,notice_html' % code)
        if st >= 400 or not isinstance(rows, list) or not rows:
            print('%-8s ✗ 读取失败 %s %s' % (code, st, rows))
            continue
        row = rows[0]
        v = row.get('verdict_html') or ''
        old_notice = row.get('notice_html') or ''
        print('%-8s %s   结论 %d 字 → ' % (code, row.get('name') or '', len(v)), end='')

        segs, nv = [], v
        for pat in STRIP[code]:
            m = re.search(pat, nv, re.S)
            if not m:
                print('\n   ⚠️ 未命中（可能已处理过）：%s' % pat[:52], end='')
                continue
            seg = m.group(0)
            seg = re.sub(r'^(?:\s*<br\s*/?>\s*)+', '', seg).strip()
            segs.append(seg)
            nv = nv[:m.start()] + nv[m.end():]
        nv = re.sub(r'(?:\s*<br\s*/?>\s*){2,}', '<br><br>', nv)
        nv = re.sub(r'\s*<br\s*/?>\s*$', '', nv).strip()

        if code in NEW_VERDICT:
            nv = NEW_VERDICT[code]

        notice = ('<p>' + '</p><p>'.join(segs) + '</p>') if segs else None
        if notice and old_notice:
            notice = old_notice + notice          # 已有说明就往后追加，不覆盖
        elif not notice:
            notice = None

        print('%d 字' % len(nv))
        if segs:
            print('   切出注解 → notice_html（%d 段，%d 字）：' % (len(segs), len(notice or '')))
            for s in segs:
                print('     · %s' % plain(s)[:88])
        else:
            print('   无注解可切')
        print('   新结论首 70 字：%s' % plain(nv)[:70])

        payload = {'verdict_html': nv, 'up': now}
        if notice:
            payload['notice_html'] = notice
        if dry:
            changed += 1
            continue

        st, r = req('wb_reports?id=eq.%s' % row.get('id', code), 'PATCH', payload)
        if st >= 400:
            print('   ✗ 写库失败 %s %s' % (st, r))
        else:
            changed += 1
            print('   ✓ 已写入（http %s）' % st)
        print('-' * 100)

    print('=' * 100)
    print('%s %d 篇' % ('待改动' if dry else '已改动', changed))


if __name__ == '__main__':
    main()
