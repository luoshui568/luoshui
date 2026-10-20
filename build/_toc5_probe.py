# -*- coding: utf-8 -*-
"""第五版目录体检：几何 / 竖线变量 / 三档断点 / tocSpy 读数 / 表格溢出 / hover 规则。

用法：python build/_toc5_probe.py [HTML]      # 默认 _work/p5_prev.html
读数走「注入脚本 → 写进 <title> → --dump-dom 抓回」，不依赖截图。
"""
import io
import json
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EDGE = '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge'
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, '_work/p5_prev.html')
TMP = os.path.join(ROOT, '_work/probe_toc5.html')
TITLE = os.path.join(ROOT, '_work/probe_toc5.dom')
UD = os.path.join(ROOT, '_work/edge-probe')

JS = r"""
<script>
(function(){
  function cs(el,p){ return getComputedStyle(el).getPropertyValue(p).trim(); }
  function round(n){ return Math.round(n*100)/100; }
  function tick(){
    var out = {}, nav = document.querySelector('nav.toc');
    if(!nav){ document.title = 'PROBE:{"fatal":"no nav.toc"}'; return; }
    var r = nav.getBoundingClientRect();
    var wrap = document.querySelector('.wrap');
    var wr = wrap.getBoundingClientRect();
    out.nav = {w: round(r.width), left: round(r.left), right: round(r.right),
               h: round(r.height)};
    out.wrap = {left: round(wr.left), pad: cs(wrap,'padding-left'),
                contentLeft: round(wr.left + parseFloat(cs(wrap,'padding-left'))),
                maxW: cs(wrap,'max-width')};
    out.gapToContent = round(out.wrap.contentLeft - out.nav.right);

    var pf = getComputedStyle(nav, '::before');
    /* 竖线已下线（2026-10-20）：::before 不该再有任何生成内容 */
    out.line = {content: pf.content, display: pf.display, bgImage: pf.backgroundImage.slice(0, 60)};
    out.radius = {nav: cs(nav,'border-top-left-radius'), navBr: cs(nav,'border-bottom-right-radius')};
    /* ⚠️ 必须挑**非选中**条目量背景：第一条默认就是 .on（深墨单层背景），
       拿它测会看到 1 层渐变、size 100% 100%，四条断言全假红。 */
    var aN = nav.querySelectorAll('a'), a0 = null;
    for(var q = 0; q < aN.length; q++){ if(!aN[q].classList.contains('on')){ a0 = aN[q]; break; } }
    if(a0){
      out.aRadius = cs(a0,'border-top-left-radius');
      out.aBgImage = cs(a0,'background-image');
      out.aBgSize = cs(a0,'background-size');
      out.aBgPos = cs(a0,'background-position');
      out.aAlign = cs(a0,'text-align');
      var last = aN[aN.length - 1];
      out.lastBgImage = cs(last,'background-image');
    }

    var as = nav.querySelectorAll('a');
    out.items = as.length;
    out.n = [].map.call(as, function(a){ return a.getAttribute('data-n'); }).join(',');
    out.i = [].map.call(as, function(a){ return a.getAttribute('data-i'); }).join(',');
    /* 条目不许多出 title：会在 hover 时弹浏览器原生提示条（2026-10-20 用户令删掉） */
    out.titles = [].filter.call(as, function(a){ return a.hasAttribute('title'); }).length;
    if(as.length > 1){
      out.pitch = round(as[1].offsetTop - as[0].offsetTop);
      out.itemH = round(as[0].getBoundingClientRect().height);
    }

    /* hover 规则是否在位（不能真 hover，只能读规则） */
    var hov = [], onR = [];
    for(var s = 0; s < document.styleSheets.length; s++){
      var rs; try{ rs = document.styleSheets[s].cssRules; }catch(e){ continue; }
      if(!rs) continue;
      for(var k = 0; k < rs.length; k++){
        var sel = rs[k].selectorText || '';
        var txt = rs[k].cssText || '';
        if(/^nav\.toc a:hover(::before)?$/.test(sel)) hov.push(sel + ' {' + txt + '}');
        if(/nav\.toc a\.on$/.test(sel)) onR.push(txt);
      }
    }
    out.hoverRule = hov.join(' || ').slice(0, 400);
    out.onRule = onR.join(' || ').slice(0, 260);

    /* 滚动读数：直接调 tocSpy，不依赖 scroll 事件 */
    var pts = [0, 0.25, 0.5, 0.85, 1], res = [];
    var max = Math.max(1, document.documentElement.scrollHeight - window.innerHeight);
    pts.forEach(function(p){
      window.scrollTo(0, Math.round(max * p));
      if(typeof tocSpy === 'function') tocSpy();
      var b = document.querySelector('.tc-ix b');
      var pg = document.querySelector('.tc-pg b');
      var bar = document.querySelector('.tc-bar i');
      var on = document.querySelector('nav.toc a.on');
      res.push({p: p, ix: b ? b.textContent : '', pg: pg ? pg.textContent : '',
                bar: bar ? cs(bar,'width') : '', on: on ? on.textContent.trim() : ''});
    });
    window.scrollTo(0, 0);
    if(typeof tocSpy === 'function') tocSpy();
    out.spy = res;

    /* 表格溢出（正文让位 40px 之后必须为 0） */
    var ofl = 0, tot = 0;
    document.querySelectorAll('#mods table').forEach(function(t){
      tot++;
      if(t.scrollWidth - t.clientWidth > 1) ofl++;
    });
    out.tables = tot; out.tableOverflow = ofl;

    /* 星号与两位小数 */
    out.stars = (document.querySelector('#mods').innerText.match(/\*\*/g) || []).length;

    document.title = 'PROBE:' + JSON.stringify(out);
  }
  window.addEventListener('load', function(){ setTimeout(tick, 900); });
  setTimeout(tick, 2600);
})();
</script>
"""

s = io.open(SRC, encoding='utf-8').read()
io.open(TMP, 'w', encoding='utf-8').write(s.replace('</body>', JS + '</body>'))


def dump(w, h):
    cmd = [EDGE, '--headless=new', '--disable-gpu', '--no-sandbox',
           '--no-proxy-server', '--user-data-dir=' + UD,
           '--window-size=%d,%d' % (w, h),
           '--virtual-time-budget=9000', '--dump-dom', 'file://' + TMP]
    r = subprocess.run(cmd, capture_output=True, text=True)
    io.open(TITLE, 'w', encoding='utf-8').write(r.stdout)
    m = re.search(r'<title>PROBE:(.*?)</title>', r.stdout, re.S)
    if not m:
        print('❌ 取不到读数（%d 字节 DOM）' % len(r.stdout))
        return None
    return json.loads(m.group(1))


ok = True


def chk(cond, msg, got=''):
    global ok
    if not cond:
        ok = False
    print('%s %s%s' % ('  ✓' if cond else '  ✗', msg, ('  → ' + str(got)) if got != '' else ''))


print('=== 1440×900（完整竖排，178 宽） ===')
d = dump(1440, 900)
if d:
    nav, line, spy = d['nav'], d['line'], d['spy']
    chk(abs(nav['w'] - 178) < 1, '目录宽 178', nav['w'])
    chk(nav['left'] >= 8, '左边距 ≥ 8px', nav['left'])
    chk(6 <= d['gapToContent'] <= 14, '与正文内容间距 6~14px', d['gapToContent'])
    chk(line['content'] in ('none', 'normal'), '竖线已移除（::before 无内容）', line['content'])
    chk(d['radius']['nav'] == '0px' and d['radius']['navBr'] == '0px',
        '卡片四角是方的（radius 0）', d['radius']['nav'] + ' / ' + d['radius']['navBr'])
    chk(d['aRadius'] == '0px', '条目方角', d['aRadius'])
    bgs = d['aBgImage'].count('linear-gradient')
    chk(bgs == 2, '条目双层背景（下划线 + hover 金带）', bgs)
    chk('rgba(192, 57, 43' in d['aBgImage'] and 'rgba(193, 145, 31' in d['aBgImage'],
        '下划线是红→金渐变', d['aBgImage'][:100])
    chk(d['aBgSize'].split(',')[0].strip().endswith('2px'), '下划线加粗到 2px', d['aBgSize'])
    chk(d['aBgPos'].split(',')[0].strip() in ('50% 100%', 'center bottom', '50% 100%'),
        '下划线左右对称（居中）', d['aBgPos'])
    chk(d['aAlign'] == 'center', '条目标题文字居中', d['aAlign'])
    chk(d['lastBgImage'] == 'none', '最后一条不画线（避免与进度区分隔线成双）', d['lastBgImage'])
    # computed cssText 会把 box-shadow 规范成 `rgba(...) 3px 0px 0px -1px inset`，
    # 所以只判「有 inset / 没有 translateX」，别去比对字面量顺序。
    chk('background-size' in d['hoverRule'] and 'inset' in d['hoverRule']
        and 'translateX' not in d['hoverRule'],
        'hover：光带展开 + 左侧金柱，且不再位移', d['hoverRule'][:70])
    chk('::before' in d['hoverRule'] and 'scale(1.12)' in d['hoverRule'],
        'hover：序号变金放大（::before 规则在位）')
    chk('linear-gradient' in d['onRule'] and '100% 100%' in d['onRule'],
        '选中：深墨块 + 光带不打折', d['onRule'][:60])
    chk(d['items'] == 10 and d['n'].startswith('01,02') and d['i'].startswith('1,2'),
        '10 条、data-n 补零 / data-i 纯数字', d['n'])
    chk(d['titles'] == 0, '条目无 title（不弹原生提示条）', d['titles'])
    chk(d['tableOverflow'] == 0, '表格 0 溢出（共 %d 张）' % d['tables'])
    chk(d['stars'] == 0, '#mods 内 0 个残余 **')
    pgs = [x['pg'] for x in spy]
    chk(pgs[0] in ('0%', '1%') and pgs[-1] in ('99%', '100%'),
        '阅读进度 0% → 100%', ' / '.join(pgs))
    chk(len(set(x['ix'] for x in spy)) >= 3, '序号随滚动变化',
        ' → '.join(x['ix'] for x in spy))
    chk(spy[-1]['on'] == '企业评分', '末条高亮 = 企业评分', spy[-1]['on'])
    chk(spy[2]['on'] not in ('', None), '中段有条目高亮', spy[2]['on'])

print('=== 1200×900（胶囊态） ===')
d2 = dump(1200, 900)
if d2:
    chk(d2['nav']['w'] < 60, '收起为 46 宽胶囊', d2['nav']['w'])
    chk(d2['line']['content'] in ('none', 'normal'), '胶囊态同样没有竖线（无生成内容）',
        d2['line']['content'])
    chk(d2['gapToContent'] > 0, '胶囊不压正文', d2['gapToContent'])

print('=== 390×844（底部横排条） ===')
d3 = dump(390, 844)
if d3:
    chk(d3['nav']['w'] > 300, '底部条铺满宽度', d3['nav']['w'])
    chk(d3['nav']['h'] < 80, '底部条高度 < 80', d3['nav']['h'])

print()
print('总分：%s' % ('全绿 ✓' if ok else '有红 ✗'))
sys.exit(0 if ok else 1)
