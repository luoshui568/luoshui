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
    out.line = {
      content: pf.content, display: pf.display, left: pf.left, width: pf.width, top: pf.top,
      height: pf.height, opacity: pf.opacity,
      bgImage: pf.backgroundImage.slice(0, 110),
      mask: (pf.webkitMaskImage || pf.maskImage || '').slice(0, 130),
      stepVar: nav.style.getPropertyValue('--tc-step'),
      ltVar: nav.style.getPropertyValue('--tc-lt'),
      lhVar: nav.style.getPropertyValue('--tc-lh')
    };

    var as = nav.querySelectorAll('a');
    out.items = as.length;
    out.n = [].map.call(as, function(a){ return a.getAttribute('data-n'); }).join(',');
    out.i = [].map.call(as, function(a){ return a.getAttribute('data-i'); }).join(',');
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
    chk(line['content'] == '""', '竖线伪元素存在', line['content'])
    chk(line['width'] in ('1px', '1.09px', '1.09px'), '线宽 1px', line['width'])
    chk('linear-gradient' in line['bgImage'] and 'rgb(192, 57, 43)' in line['bgImage'],
        '红→金渐变在 background-image 上', line['bgImage'][:70])
    chk('repeating-linear-gradient' in line['mask'], '虚线靠 mask 切', line['mask'][:60])
    nums = [float(x) for x in re.findall(r'([\d.]+)px', line['mask'])]
    step = float(line['stepVar'][:-2]) if line['stepVar'].endswith('px') else 0
    chk(len(nums) >= 4 and abs(nums[-1] - step) < 0.6 and abs(nums[-1] - nums[-2] - 5) < 0.6,
        '竖线：周期 = --tc-step，每行只留 5px 缺口', line['mask'])
    chk(line['stepVar'].endswith('px') and float(line['stepVar'][:-2]) > 30,
        '--tc-step 已写入且 > 30px', line['stepVar'])
    chk(line['ltVar'].endswith('px') and line['lhVar'].endswith('px'),
        '--tc-lt/--tc-lh 已写入', line['ltVar'] + ' / ' + line['lhVar'])
    chk(abs(float(line['lhVar'][:-2]) - d['pitch'] * (d['items'] - 1)) < 2,
        '线长 = 首末条目中线距离', '%s vs %d×%d' % (line['lhVar'], d['pitch'], d['items'] - 1))
    chk('translateX(3px)' in d['hoverRule'] and 'background-size' in d['hoverRule'],
        'hover：光带展开 + 右移（规则在位）', d['hoverRule'][:60])
    chk('::before' in d['hoverRule'] and 'scale(1.12)' in d['hoverRule'],
        'hover：序号变金放大（::before 规则在位）')
    chk('linear-gradient' in d['onRule'] and '100% 100%' in d['onRule'],
        '选中：深墨块 + 光带不打折', d['onRule'][:60])
    chk(d['items'] == 10 and d['n'].startswith('01,02') and d['i'].startswith('1,2'),
        '10 条、data-n 补零 / data-i 纯数字', d['n'])
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
    chk(d2['line']['display'] == 'none', '胶囊态不出竖线（::before display:none）',
        d2['line']['display'])
    chk(d2['gapToContent'] > 0, '胶囊不压正文', d2['gapToContent'])

print('=== 390×844（底部横排条） ===')
d3 = dump(390, 844)
if d3:
    chk(d3['nav']['w'] > 300, '底部条铺满宽度', d3['nav']['w'])
    chk(d3['nav']['h'] < 80, '底部条高度 < 80', d3['nav']['h'])

print()
print('总分：%s' % ('全绿 ✓' if ok else '有红 ✗'))
sys.exit(0 if ok else 1)
