# -*- coding: utf-8 -*-
"""槽 29「动态调整」交互自测（无头）—— 真拖、真改、真恢复。

为什么要写它：交互件是**运行时生成**的（`node --check` 只能保证语法），
而线上页 headless 打不开（导航被拦成风险提醒页）⇒ 只能自己搭台子跑。

做法：把 `report_theme.css` + 壳里的 `scoreLive` 段 + **线上真实的模块 HTML**
      拼成一个最小页，页面里的驱动脚本模拟三种输入（改分数 / 拖进度条 / 键盘），
      把每个动作后的状态写进 `<pre id="sc-test-out">`，再用 `--dump-dom` 取回来，
      **在 Python 侧用冻结表独立复算**总分 —— 两边必须逐字相等（页面 vs 后端）。

三个用例：
  A 线上原文（旧渲染，无 data-w）→ 走「解析 .sc-w 文本」兜底路径
  B 注入 data-w 后（新渲染）    → 必须与 A 得到同一个初评总分
  C 空分形态                    → 未评分项按中性 6 分计，实时条上要有这句

用法： python _sc_test.py [--code 002408] [--keep]
"""
import base64
import io
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEPLOY = os.path.join(ROOT, 'deploy')
EDGE = r'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'
EDGE2 = r'C:/Program Files/Microsoft/Edge/Application/msedge.exe'

import score_lock as SL                                        # noqa: E402
import _score_patch as SP                                      # noqa: E402
from _apply_score import get_live                               # noqa: E402


def score_js():
    """从模板里挖出 scoreLive 那一段（从注释块头到 renderFoot 之前）。"""
    tpl = io.open(os.path.join(DEPLOY, 'report.template.html'), encoding='utf-8').read()
    b = tpl.find('槽 29「企业评分」动态调整（2026-09-22 用户令）')
    if b < 0:
        sys.exit('✗ 模板里找不到 scoreLive 段（注释标题变了？）')
    a = tpl.rfind('/* ------', 0, b)
    e = tpl.find('function renderFoot(){', b)
    js = tpl[a:e]
    for need in ('function scoreLive', 'function scWireLine', 'function scPaint',
                 'function scNote', 'function scCopyFallback',
                 'function scBuildHtml', 'function scNoteSentence',
                 'function scNoteConsistent', 'function scTotalW'):
        if need not in js:
            sys.exit('✗ 抽出来的 JS 段不完整：缺 %s' % need)
    return js


DRIVER = r"""
var RES = {errors: []};
/* ★ 产出 HTML 必须用 base64 传回：直接塞进 DOM 文本再 --dump-dom，浏览器会把
   `<` 序列化成 `&lt;`，两边就不是同一串字节了（第一次跑就吃了这个亏）。
   base64 里只有 A-Za-z0-9+/=，怎么序列化都不变。 */
function b64(str){
  var bytes = new TextEncoder().encode(str), bin = '';
  for(var i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
  return btoa(bin);
}
function card(sec){ return document.querySelector('[data-mod="' + sec + '"]'); }
function snap(sec){
  var o = {}, c = card(sec);
  var num = c.querySelector('.gauge-num'), bd = c.querySelector('.gauge-badge'),
      tn = c.querySelector('.sc-total .tn'), tt = c.querySelector('.sc-total .tt');
  o.num = num ? num.textContent.trim() : null;
  o.badge = bd ? bd.textContent.trim() : null;
  o.tn = tn ? tn.textContent.trim() : null;
  o.tt = tt ? tt.textContent.trim() : null;
  o.scores = []; o.widths = []; o.cls = []; o.knob = []; o.ph = [];
  var is = c.querySelectorAll('.sc-inp');
  for(var i = 0; i < is.length; i++){
    o.scores.push(is[i].value);
    o.ph.push(is[i].placeholder);
    var bar = is[i].closest('.sc-line').querySelector('.sc-bar');
    var f = bar.firstElementChild;
    o.widths.push(f ? f.style.width : null);
    o.cls.push(f ? f.className : null);
    o.knob.push(bar.style.getPropertyValue('--scp'));
  }
  var crit = c.querySelector('.criteria');
  /* ⚠️ 不能直接 querySelector('p.src') —— 母本 600456 的模块**开头**还有一个 p.src
     （口径段），取第一个会取错。控件用的是「.criteria 的下一个 p.src」，这里必须同口径。 */
  var src = crit ? crit.nextElementSibling : null;
  while(src && !(src.tagName === 'P' && /\bsrc\b/.test(src.className || ''))) src = src.nextElementSibling;
  o.srcFound = !!src;
  /* ★ 用稳定标记判「已改成临时调整版」，别匹配散文措辞 —— 措辞一改断言就假失败
     （2026-09-22 把「本地预览」改成「尚未提交」时踩过）。 */
  o.srcDynamic = !!(src && src.getAttribute('data-sc-dyn') === '1');
  o.srcHasNamed = !!(src && src.textContent.indexOf('主要得分项为') >= 0);
  o.srcLen = src ? src.textContent.length : 0;
  o.live = c.querySelectorAll('.criteria.sc-live').length;
  o.wired = crit ? crit.getAttribute('data-sc-wired') : null;
  /* ★ 布局完整性：实时条曾经叫 `.sc-live`，与评分卡状态类撞名 ⇒ `.sc-live{display:flex}`
     把 .criteria 本身变成 flex 容器，标题条被压成 168px、总分条并排跑。
     这里把「没被带歪」变成硬断言，下次谁再撞名会立刻炸。 */
  o.livebarN = c.querySelectorAll('.sc-livebar').length;
  o.critDisp = crit ? getComputedStyle(crit).display : null;
  o.critW = crit ? Math.round(crit.getBoundingClientRect().width) : null;
  var hd = c.querySelector('.criteria-head'), ln0 = c.querySelector('.sc-line');
  o.headW = hd ? Math.round(hd.getBoundingClientRect().width) : null;
  o.lineW = ln0 ? Math.round(ln0.getBoundingClientRect().width) : null;
  function shown(sel){ var el = c.querySelector(sel); return el ? (el.style.display !== 'none') : null; }
  o.dirtyChip = shown('.lv-dirty'); o.resetBtn = shown('.lv-reset');
  o.saveBtn = shown('.lv-save');
  o.baseChip = shown('.lv-base'); o.blankChip = shown('.lv-blank');
  var bc = c.querySelector('.lv-base');
  o.baseText = bc ? bc.textContent.trim() : null;
  var dc = c.querySelector('.lv-dirty b');
  o.dirtyText = dc ? dc.textContent.trim() : null;
  var g = c.querySelector('.gauge');
  o.gauge = g ? g.style.background : null;
  o.gwDirty = c.querySelectorAll('.gauge-wrap.sc-dirty').length;
  o.wiredRows = c.querySelectorAll('.sc-bar[role="slider"]').length;
  return o;
}
function setInp(sec, idx, v){
  var inp = card(sec).querySelectorAll('.sc-inp')[idx];
  inp.value = v;
  inp.dispatchEvent(new Event('input', {bubbles: true}));
  inp.dispatchEvent(new Event('change', {bubbles: true}));
}
function drag(sec, idx, frac){
  var bar = card(sec).querySelectorAll('.sc-bar')[idx];
  var r = bar.getBoundingClientRect();
  var o = {bubbles: true, cancelable: true, pointerId: 7, pointerType: 'mouse',
           button: 0, buttons: 1, clientX: r.left + r.width * frac,
           clientY: r.top + r.height / 2};
  try{
    bar.dispatchEvent(new PointerEvent('pointerdown', o));
    bar.dispatchEvent(new PointerEvent('pointermove', o));
    bar.dispatchEvent(new PointerEvent('pointerup', o));
  }catch(e){
    try{
      var m = new MouseEvent('pointerdown', o);
      m.pointerId = 7; bar.dispatchEvent(m);
      bar.dispatchEvent(new MouseEvent('pointerup', o));
    }catch(e2){ RES.errors.push('drag: ' + e2.message); }
  }
  return {left: Math.round(r.left), width: Math.round(r.width)};
}
function key(sec, idx, k){
  var bar = card(sec).querySelectorAll('.sc-bar')[idx];
  bar.dispatchEvent(new KeyboardEvent('keydown', {bubbles: true, cancelable: true, key: k}));
}
function clickReset(sec){
  var b = card(sec).querySelector('.lv-reset');
  if(b) b.click(); else RES.errors.push('no reset btn ' + sec);
}
try{
  var MODS = scoreLive(document);
  RES.mods = MODS.length;

  RES.cfg = SC_T;
  RES.A0 = snap('A');
  setInp('A', SC_T.ti, SC_T.tv);            RES.A1 = snap('A');   /* 改分数（目标值必不同于原分） */
  RES.dragRect = drag('A', SC_T.di, SC_T.df);  RES.A2 = snap('A'); /* 拖到指定比例 */
  RES.dragRect2 = drag('A', SC_T.d2i, SC_T.d2f); RES.A2b = snap('A');
  /* 键盘方向按**当时的值**定：已是 10 分就按 ↓，否则 ↑（都不写死） */
  RES.keyFrom = parseInt(card('A').querySelectorAll('.sc-inp')[0].value, 10);
  RES.keyDir = (RES.keyFrom >= 10 ? 'ArrowDown' : 'ArrowUp');
  key('A', 0, RES.keyDir);                  RES.A3 = snap('A');
  clickReset('A');                          RES.A4 = snap('A');   /* 恢复初评 */

  RES.B0 = snap('B');                                     /* data-w 路径 */
  RES.C0 = snap('C');                                     /* 空分形态 */
  setInp('C', 0, 10);            RES.C1 = snap('C');
  clickReset('C');               RES.C2 = snap('C');

  /* —— 用例 D：落库字节比对 ——
     调用与线上「💾 提交到数据库」**完全同一个** scBuildHtml()，把产出原样带回 Python，
     与后端 _score_patch.apply_scores() 的输出逐字比。两边不等 = 页面写的与脚本写的不是一套。 */
  var mD = MODS[0];
  RES.D_modHtmlLen = mD ? (mD.html || '').length : -1;
  if(mD){
    var D = mD.cur.slice();
    for(var q = 0; q < 10; q++){ if(D[q] === null) D[q] = 0; }   /* 落库只接受 0-10 整数 */
    D[SC_T.di] = (D[SC_T.di] === 10 ? 4 : 10);                   /* 保证与当前值不同 */
    RES.D_scores = D;
    try{ RES.D_html_b64 = b64(scBuildHtml(mD, D)); }
    catch(e){ RES.D_html_b64 = null; RES.errors.push('scBuildHtml: ' + e.message); }

    /* —— 用例 E：拿**原分**提交一次，必须与线上原文逐字节相同 ——
       这是「不改分就不会动库」的直接证据，也是母本那句手写点名句得以保留的保证。 */
    try{
      var E = mD.cur.slice();
      RES.E_ok = (E.indexOf(null) < 0);
      RES.E_scores = E;
      RES.E_html_b64 = RES.E_ok ? b64(scBuildHtml(mD, E)) : null;
    }catch(e){ RES.E_html_b64 = null; RES.errors.push('E: ' + e.message); }
  }
}catch(e){ RES.errors.push('driver: ' + (e && e.message)); }
document.getElementById('sc-test-out').textContent = JSON.stringify(RES);
"""


def build_page(code, live_html, blank_html, cfg):
    css = io.open(os.path.join(HERE, 'report_theme.css'), encoding='utf-8').read()
    js = score_js()
    # B：把 data-w 注入进去（模拟 score_lock v2 的新渲染）
    b_html = re.sub(r'class="sc-line"',
                    lambda m, it=iter([w for _, _, w in SL.ITEMS]):
                    'class="sc-line" data-w="%d"' % next(it), live_html)
    secs = [('A', '线上原文（旧渲染 · 无 data-w）', live_html),
            ('B', '注入 data-w（新渲染）', b_html),
            ('C', '空分形态（十项全「—」）', blank_html)]
    parts = []
    for sid, ttl, h in secs:
        parts.append('<div class="card" id="m29%s" data-mod="%s">'
                     '<h2><span class="no">29</span>企业评分</h2>%s</div>'
                     '<p style="font:12px sans-serif;color:#888;margin:6px 0 26px">'
                     '用例 %s：%s</p>' % (sid, sid, h, sid, ttl))
    page = ('<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">'
            '<title>槽29 动态调整自测</title><style>' + css +
            '\nbody{background:#fafafa;padding:20px;max-width:1240px;margin:0 auto;}</style>'
            '</head><body>\n' + '\n'.join(parts) +
            '\n<pre id="sc-test-out" style="display:none"></pre>\n'
            # ★ 造一个 St.mods：scWire 靠它取「模块原文」当落库底稿。
            #   给的就是**线上真实 html** —— 用例 D 才有得比。
            '<script>var St = ' + json.dumps({
                'code': code, 'rep': {},
                'mods': [{'id': sid, 'no': '29', 'html': h} for sid, _, h in secs]
            }, ensure_ascii=False) + ';</script>\n'
            '<script>var SC_T = ' + json.dumps(cfg) + ';</script>\n'
            '<script>' + js + '</script>\n'
            '<script>' + DRIVER + '</script>\n</body></html>')
    out = os.path.join(HERE, '_sc_test.html')
    io.open(out, 'w', encoding='utf-8').write(page)
    return out


def total_of(scores):
    """后端口径独立复算：未评分项按中性 6 分补齐，再走 score_lock 的母本公式。"""
    return SL.total_of([SL.NEUTRAL if s is None else s for s in scores])


def main():
    code = '002408'
    if '--code' in sys.argv:
        code = sys.argv[sys.argv.index('--code') + 1]
    row = get_live(code) or {}
    live = row.get('html') or ''
    if not live:
        sys.exit('✗ 取不到线上 %s 的槽 29' % code)
    # ★ 取分改走 _score_patch.parse_scores —— 它会做一致性判据：
    #   `.sc-val` 算出的总分与存储总分对不上时改按**条宽**读并给出 warn。
    #   （母本 600456 第 10 项 `.sc-val` 是 5、条宽是 60%、总分 70.5 ⇒ 文本格是笔误。）
    base_scores, base_src, base_warn = SP.parse_scores(live)
    if not base_scores:
        sys.exit('✗ 线上原文读不出十项分数（非有分形态？），换个 code')
    stored_total = SP.parse_stored_total(live)
    for w in base_warn:
        print('⚠ %s' % w)
    blank = SL.render(kpi={}, period='2026H1')
    # 用例参数按**这家的实际分数**定 —— 目标值必须与原分不同，否则「改分」等于没改，
    # dirty 类断言会假失败（广信 603599 第 3 项本来就是 10 分，踩过）。
    ti = next((i for i in range(10) if base_scores[i] != 10), 0)
    tv = 10 if base_scores[ti] != 10 else 5
    d1 = next(i for i in range(10) if i != ti)
    d2 = next((i for i, v in enumerate(base_scores) if v not in (3, 10) and i != ti), d1)
    cfg = {'ti': ti, 'tv': tv, 'di': d1, 'df': 0.7, 'd2i': d2, 'd2f': 0.3}
    page = build_page(code, live, blank, cfg)
    print('用例页 %s（%d 字节）｜ %s 初评 %s' %
          (os.path.relpath(page, HERE), os.path.getsize(page), code, base_scores))
    print('用例参数 %s' % cfg)

    edge = EDGE if os.path.exists(EDGE) else EDGE2
    if not os.path.exists(edge):
        sys.exit('✗ 找不到 Edge')
    dom = subprocess.run([edge, '--headless=new', '--disable-gpu', '--no-sandbox',
                          '--hide-scrollbars', '--force-device-scale-factor=1',
                          '--window-size=1300,3000', '--virtual-time-budget=5000',
                          '--dump-dom', 'file:///' + page.replace('\\', '/')],
                         capture_output=True, text=True, encoding='utf-8',
                         errors='replace')
    m = re.search(r'<pre id="sc-test-out"[^>]*>(.*?)</pre>', dom.stdout or '', re.S)
    if not m:
        sys.exit('✗ 取不到测试输出（页长 %d 字节）\nstderr: %s'
                 % (len(dom.stdout or ''), (dom.stderr or '')[:600]))
    res = json.loads(m.group(1))
    if res.get('errors'):
        print('驱动报错：', res['errors'])

    ok = True

    def chk(cond, msg):
        nonlocal ok
        print('  %s %s' % ('✓' if cond else '✗', msg))
        if not cond:
            ok = False

    print('\n=== 用例 A：线上原文（旧渲染，走 .sc-w 文本兜底） ===')
    a0 = res['A0']
    chk(a0['live'] == 1 and a0['wired'] == '1',
        '评分卡已接管（sc-live ×%s / data-sc-wired=%s）' % (a0['live'], a0['wired']))
    chk(a0['wiredRows'] == 10, '十行都装上了 role=slider（%s）' % a0['wiredRows'])
    chk(a0['livebarN'] == 1, '卡片里只有一条实时条（%s）' % a0['livebarN'])
    chk(a0['critDisp'] != 'flex',
        '评分卡没被实时条的 display:flex 带歪（display=%s）' % a0['critDisp'])
    chk(a0['headW'] is not None and abs(a0['headW'] - a0['critW']) <= 4,
        '标题条仍占满卡片宽（head %s / crit %s / 评分行 %s）'
        % (a0['headW'], a0['critW'], a0['lineW']))
    chk([int(x) for x in a0['scores']] == base_scores,
        '分数框回填与线上一致 %s' % a0['scores'])
    chk(float(a0['num'].split('/')[0]) == total_of(base_scores),
        '初评总分 %s（后端复算 %s）' % (a0['num'], total_of(base_scores)))
    # ★★ 这条是「标尺」断言，必须有：上面那条只是「页面 == 页面自己取的源」，
    #    源本身写错时它照样绿（母本 600456 第 10 项 `.sc-val` 笔误就是这么溜过去的：
    #    页面把静态 70.5 改写成 69.9，而两条自洽断言全都通过）。这里改成拿**库里的静态总分**
    #    当标尺 —— 页面显示的总分必须等于库里写着的那一个。
    chk(stored_total is not None and float(a0['num'].split('/')[0]) == stored_total,
        '★ 页面初评总分 == 线上静态总分 %s（拿库里的数当标尺）' % stored_total)
    chk(base_src == 'val' or SP.parse_stored_total(live) == total_of(base_scores),
        '取分来源 %s（与存储总分自洽）' % base_src)
    chk(a0['badge'] == '评级 · ' + SL.grade_of(total_of(base_scores)),
        '徽标 %s' % a0['badge'])
    chk(a0['baseChip'] and a0['baseText'] == '初评 %s' % a0['num'].split('/')[0],
        '初评 chip「%s」' % a0['baseText'])
    chk(a0['dirtyChip'] is False and a0['resetBtn'] is False,
        '未调整时「已调整 / 恢复初评」都不出现')
    chk(a0['saveBtn'] is False,
        '未调整时「💾 提交到数据库」不出现（没改动就没什么可提交）')
    chk(a0['srcDynamic'] is False, '未调整时评分说明段保持线上原文')
    chk(a0['gwDirty'] == 0, '环形卡未转红')

    k = cfg['ti']
    print('\n=== 改分（第 %d 项 %s → %s） ===' % (k + 1, base_scores[k], cfg['tv']))
    exp = base_scores[:]; exp[k] = cfg['tv']
    a1 = res['A1']
    chk(float(a1['num'].split('/')[0]) == total_of(exp),
        '总分 %s（后端复算 %s）' % (a1['num'], total_of(exp)))
    chk(a1['tn'] == a1['num'].split('/')[0], '总分条 %s 与环形卡一致' % a1['tn'])
    chk(a1['scores'][k] == str(cfg['tv']), '分数框 %s' % a1['scores'][k])
    chk(a1['cls'][k].split()[0] in ('hi', 'mid', 'low')
        and a1['widths'][k] == '%d%%' % (exp[k] * 10),
        '第 %d 条进度条 %s 宽 %s' % (k + 1, a1['cls'][k], a1['widths'][k]))
    chk(a1['knob'][k] == '%d%%' % (exp[k] * 10), '手柄位置 %s' % a1['knob'][k])
    chk(a1['dirtyChip'] and a1['resetBtn'] and a1['gwDirty'] == 1,
        '「已调整」chip + 恢复按钮 + 徽标转红 齐了')
    chk(a1['saveBtn'] is True,
        '★「💾 提交到数据库」按钮随之出现（这就是本轮的交付：改完能落库）')
    chk(a1['dirtyText'] == a1['num'].split('/')[0], '「已调整 → %s」' % a1['dirtyText'])
    chk(a1['srcDynamic'] and a1['srcHasNamed'],
        '评分说明段已改成动态版（点名得分/扣分项）')

    d1 = cfg['di']
    print('\n=== 拖进度条（第 %d 项拖到 70%%） ===' % (d1 + 1))
    exp5 = exp[:]; exp5[d1] = 7
    a2 = res['A2']
    chk(float(a2['num'].split('/')[0]) == total_of(exp5),
        '拖动后总分 %s（后端复算 %s）｜轨道 left=%s width=%s'
        % (a2['num'], total_of(exp5), res['dragRect']['left'], res['dragRect']['width']))
    chk(a2['scores'][d1] == '7', '分数框跟着变成 %s' % a2['scores'][d1])

    d2 = cfg['d2i']
    print('\n=== 拖进度条 · 真变化（第 %d 项 %s 分 → 拖到 30%% ⇒ 3 分） ==='
          % (d2 + 1, base_scores[d2]))
    exp4 = exp5[:]; exp4[d2] = 3
    a2b = res['A2b']
    chk(a2b['scores'][d2] == '3', '第 %d 项 → 3' % (d2 + 1))
    chk(float(a2b['num'].split('/')[0]) == total_of(exp4),
        '总分 %s（后端复算 %s）｜轨道 left=%s width=%s'
        % (a2b['num'], total_of(exp4), res['dragRect2']['left'], res['dragRect2']['width']))
    chk('low' in (a2b['cls'][d2] or ''), '3 分的条转 low 档（%s）' % a2b['cls'][d2])

    print('\n=== 键盘 %s（第 1 项） ===' % res['keyDir'])
    exp1 = exp4[:]
    exp1[0] = max(0, min(10, res['keyFrom'] + (-1 if res['keyDir'] == 'ArrowDown' else 1)))
    a3 = res['A3']
    chk(int(a3['scores'][0]) == exp1[0], '第 1 项 %s → %s' % (res['keyFrom'], a3['scores'][0]))
    chk(float(a3['num'].split('/')[0]) == total_of(exp1),
        '总分 %s（后端复算 %s）' % (a3['num'], total_of(exp1)))

    print('\n=== 恢复初评 ===')
    a4 = res['A4']
    chk([int(x) for x in a4['scores']] == base_scores, '十项全部回到 %s' % a4['scores'])
    chk(float(a4['num'].split('/')[0]) == total_of(base_scores),
        '总分回到 %s' % a4['num'])
    chk(a4['dirtyChip'] is False and a4['resetBtn'] is False and a4['gwDirty'] == 0,
        '「已调整 / 恢复按钮 / 红徽标」都收回')
    chk(a4['saveBtn'] is False, '恢复初评后「💾 提交到数据库」也收回')
    chk(a4['srcDynamic'] is False, '评分说明段还原成线上原文')

    print('\n=== 用例 B：注入 data-w（新渲染路径） ===')
    b0 = res['B0']
    chk(b0['wired'] == '1', '已接管')
    chk(b0['num'] == a0['num'],
        '与旧渲染得到同一个初评总分：%s vs %s' % (b0['num'], a0['num']))

    print('\n=== 用例 C：空分形态（未评分项按中性 6 分） ===')
    c0 = res['C0']
    chk(c0['wired'] == '1', '空分也能接管')
    chk(c0['num'] == '—/100' and c0['badge'] == '待评分',
        '未填任何分时保持「%s / %s」' % (c0['num'], c0['badge']))
    chk(c0['baseChip'] is False, '空分不显示「初评」chip')
    chk(c0['saveBtn'] is False, '空分形态也不出现「💾 提交到数据库」（还没分可提交）')
    chk(c0['scores'] == [''] * 10 and c0['ph'] == ['6'] * 10,
        '十行留空、placeholder 提示基准 6（%s/%s）' % (c0['scores'][:2], c0['ph'][:2]))
    chk(all('guess' in (x or '') for x in c0['cls']), '未评分行的条打 guess（半透明）')
    c1 = res['C1']
    expc = [None] * 10; expc[0] = 10
    chk(float(c1['num'].split('/')[0]) == total_of(expc),
        '填第 1 项 =10 后总分 %s（后端按中性 6 复算 %s）' % (c1['num'], total_of(expc)))
    chk(c1['blankChip'] is True, '实时条提示「未评分项按中性 6 分计」')
    chk(c1['scores'] == ['10'] + [''] * 9, '其余九项仍然留空 %s' % c1['scores'])
    chk('guess' not in (c1['cls'][0] or '') and all('guess' in x for x in c1['cls'][1:]),
        '已评那行的条不再半透明')
    c2 = res['C2']
    chk(c2['num'] == '—/100' and c2['badge'] == '待评分', '恢复后又回到待评分')

    print('\n=== 用例 D：落库字节比对（页面变换 vs 后端变换） ===')
    chk(res.get('mods') == 3, '三张评分卡都接管了（%s）' % res.get('mods'))
    chk(res.get('D_modHtmlLen') == len(live),
        '页面拿到的模块原文长度与线上一致（%s vs %s）'
        % (res.get('D_modHtmlLen'), len(live)))
    d_sc = res.get('D_scores')
    d_b64 = res.get('D_html_b64')
    d_html = None
    if d_b64:
        try:
            d_html = base64.b64decode(d_b64).decode('utf-8')
        except Exception as e:
            print('      ✗ base64 解不开：%s' % e)
    chk(bool(d_sc) and len(d_sc) == 10 and all(isinstance(x, int) for x in d_sc),
        '驱动给出十项整数分数 %s' % d_sc)
    if d_sc and d_html:
        want, meta = SP.apply_scores(live, d_sc)
        chk(d_html == want,
            '★ 页面 scBuildHtml 与后端 apply_scores 逐字相等'
            '（%d vs %d 字节 · 总分 %s / %s）'
            % (len(d_html), len(want), meta['total'], meta['rating']))
        if d_html != want:
            at = SP.first_diff(want, d_html)
            print('        后端 …%s…' % want[max(0, at - 60):at + 60].replace('\n', '⏎'))
            print('        页面 …%s…' % d_html[max(0, at - 60):at + 60].replace('\n', '⏎'))
        chk(d_html.count('class="kv"') == live.count('class="kv"')
            and d_html.count('class="sc-note"') == live.count('class="sc-note"'),
            'KPI 格数与逐项说明格数原样（kv %d→%d / note %d→%d）'
            % (live.count('class="kv"'), d_html.count('class="kv"'),
               live.count('class="sc-note"'), d_html.count('class="sc-note"')))
        chk(live.count('data-w') == d_html.count('data-w'),
            '`data-w` 一个不多一个不少（原文 %d / 产出 %d）'
            % (live.count('data-w'), d_html.count('data-w')))
        chk(('<span class="tn">%s</span>' % SP.f1(meta['total'])) in d_html,
            '产出里底部总分 = %s' % SP.f1(meta['total']))
        chk(('评级：' + meta['rating']) in d_html, '产出里评级 = %s' % meta['rating'])
        again, _ = SP.apply_scores(d_html, d_sc)
        chk(again == d_html, '后端对自己产出幂等（同分再过一遍逐字节不变）')

    print('\n=== 用例 E：原分提交必须逐字节幂等（不改分就不动库） ===')
    e_b64 = res.get('E_html_b64')
    e_html = None
    if e_b64:
        try:
            e_html = base64.b64decode(e_b64).decode('utf-8')
        except Exception as e:
            print('      ✗ base64 解不开：%s' % e)
    if res.get('E_ok') and e_html is not None:
        chk(e_html == live,
            '★ 页面上「原分提交一次」的产出 == 线上原文（%d vs %d 字节）'
            % (len(e_html), len(live)))
        if e_html != live:
            at = SP.first_diff(live, e_html)
            print('        线上 …%s…' % live[max(0, at - 60):at + 60].replace('\n', '⏎'))
            print('        页面 …%s…' % e_html[max(0, at - 60):at + 60].replace('\n', '⏎'))
        # 点名句保留：原文那句与产出那句必须一模一样（母本 600456 是手写措辞）
        def _sent(h):
            m = re.search(r'主要得分项为.*?。', h, re.S)
            return m.group(0) if m else None
        chk(_sent(e_html) is not None and _sent(e_html) == _sent(live),
            '★ 点名句原样保留（%s…）'
            % ((_sent(live) or '')[:42].replace('\n', '')))
        chk(SP.note_consistent(_sent(live) or '', res.get('E_scores') or []),
            '该点名句与当前分数自洽（所以才有资格被保留）')
    else:
        print('      （跳过：驱动没给出 E，可能十项有空值）')

    print('\n结论：%s' % ('全部通过 ✅' if ok else '有失败项 ❌'))
    if '--keep' not in sys.argv and not ok:
        io.open(os.path.join(HERE, '_sc_dom.html'), 'w', encoding='utf-8').write(dom.stdout or '')
        print('（已留 _sc_dom.html 供排查）')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
