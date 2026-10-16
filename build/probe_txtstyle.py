# -*- coding: utf-8 -*-
"""模块正文「可读性」版式 · 计算样式体检。

不做像素比对，直接读渲染后的 computedStyle —— 判据是「该变的变了、不该变的没变」：
  · 导语块   .card > .rpt-ops + p     行高 2.02 / 左金条 / 金底
  · 标题条   .card > h3（金）/ h4（红）左条 + 浅底 + 内边距
  · 正文     .card > p                 行高 1.95、正文色 #5e5b52
  · 列表     .card li / .logic .lv     与正文同色 #5e5b52（2026-10-14 第二轮再降一档）
  · 来源小字 p.src                     仍是灰色（没被正文色刷掉）
  · 粗体     .card p b                 500（降档）
  · 表格     td 里的 b                 仍是 700（表格不动）
  · 反向守卫 结论块 .verdict .vlist li  仍须 #3a382f（参照版式，不许被联动改掉）
             表格 td / 模块 h2        亮度不得 >70（防刷过头）

用法：
    REPORT_SRC=/tmp/live.html python3 build/probe_txtstyle.py 002408 603977
    REPORT_SRC=/tmp/live.html python3 build/probe_txtstyle.py 002408 --mods 1,5,19,31
"""
import http.server
import json
import os
import re
import socketserver
import subprocess
import sys
import threading

REPO = '/Users/luoshui/WorkBuddy/2026-10-10-22-59-27/luoshui'
EDGE = '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge'
SERVE = '/tmp/txtprobe_serve'
PORT = 9003

DUMP = r"""
setTimeout(function(){
  var out = {};
  try{
    var cards = document.querySelectorAll('#mods > .card');
    for(var i = 0; i < cards.length; i++){
      var c = cards[i];
      var rec = {no: c.id, kinds: []};
      var kids = c.children;
      var firstP = null, firstH3 = null, firstH4 = null, srcP = null, plainP = null, boldP = null;
      for(var k = 0; k < kids.length; k++){
        var e = kids[k], tg = e.tagName;
        if(tg === 'P'){
          if(!firstP && kids[k-1] && kids[k-1].className === 'rpt-ops' && e.className === '') firstP = e;
          if(e.className.indexOf('src') >= 0 && !srcP) srcP = e;
          if(!plainP && e.className === '' && e !== firstP) plainP = e;   /* 导语段不算正文样本 */
          if(!boldP && e.querySelector('b,strong')) boldP = e;
        }
        if(tg === 'H3' && !firstH3) firstH3 = e;
        if(tg === 'H4' && !firstH4) firstH4 = e;
      }
      function st(e){
        if(!e) return null;
        var s = getComputedStyle(e);
        return {lh: s.lineHeight, fs: s.fontSize, color: s.color, fw: s.fontWeight,
                bgl: s.borderLeftColor, blw: s.borderLeftWidth,
                bg: (s.backgroundImage && s.backgroundImage !== 'none') ? s.backgroundImage.slice(0, 60) : s.backgroundColor,
                pad: s.paddingLeft};
      }
      rec.lead = st(firstP);
      rec.h3 = st(firstH3);
      rec.h4 = st(firstH4);
      rec.src = st(srcP);
      rec.body = st(plainP);
      var bb = boldP ? boldP.querySelector('b,strong') : null;
      rec.bold = bb ? getComputedStyle(bb).fontWeight : null;
      var tdb = c.querySelector('td b, td strong, th b, th strong');
      rec.tdBold = tdb ? getComputedStyle(tdb).fontWeight : null;
      rec.nP = c.querySelectorAll(':scope > p').length;
      /* ---- ⑥ 列表 / 解读块正文：应与段落同色 #5e5b52 = rgb(94, 91, 82) ---- */
      var li = c.querySelector('ul > li, ol > li');
      rec.liColor = li ? getComputedStyle(li).color : null;
      var lib = li ? li.querySelector('b,strong') : null;
      rec.liBoldColor = lib ? getComputedStyle(lib).color : null;
      var lv = c.querySelector('.logic .lv');
      rec.lvColor = lv ? getComputedStyle(lv).color : null;
      /* 反向守卫：核心结论块是用户认可的参照版式，必须**原样不动** #3a382f */
      var vl = document.querySelector('#verdict .vlist li');
      rec.verdictLiColor = vl ? getComputedStyle(vl).color : null;
      /* 对照组：表格单元格必须**仍然深色**（不能被顺手刷灰） */
      var td = c.querySelector('td');
      rec.tdColor = td ? getComputedStyle(td).color : null;
      var h2 = c.querySelector(':scope > h2');
      rec.h2Color = h2 ? getComputedStyle(h2).color : null;
      out[c.id] = rec;
    }
  }catch(err){ out.__err = '' + err; }
  var pre = document.createElement('pre'); pre.id = 'ZD';
  pre.textContent = 'ZS' + JSON.stringify(out) + 'ZE';
  document.body.appendChild(pre);
}, 4200);
"""


class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=SERVE, **kw)

    def log_message(self, *a):
        pass


def main():
    a = sys.argv[1:]
    codes = [x for x in a if not x.startswith('--')]
    mods = a[a.index('--mods') + 1].split(',') if '--mods' in a else None
    src = os.environ.get('REPORT_SRC', os.path.join(REPO, 'deploy', 'report.html'))
    html = open(src, encoding='utf-8', errors='replace').read()
    i = html.rfind('</body>')
    os.makedirs(SERVE, exist_ok=True)
    open(os.path.join(SERVE, 'report.html'), 'w', encoding='utf-8').write(html[:i] + '<script>' + DUMP + '<' + '/script>' + html[i:])

    socketserver.TCPServer.allow_reuse_address = True
    srv = socketserver.TCPServer(('127.0.0.1', PORT), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    red, done = [], 0
    for code in codes:
        r = subprocess.run([EDGE, '--headless=new', '--no-sandbox', '--disable-gpu', '--no-proxy-server',
                            '--user-data-dir=/tmp/edgeprof_tp', '--window-size=1400,1000',
                            '--virtual-time-budget=26000', '--dump-dom',
                            'http://localhost:%d/report.html?code=%s' % (PORT, code)],
                           capture_output=True, timeout=300)
        dom = r.stdout.decode('utf-8', 'replace')
        m = re.search(r'ZS(\{.*?\})ZE', dom, re.S)
        if not m:
            print('%-8s 拿不到 dump' % code)
            red.append('%s dump' % code)
            continue
        data = json.loads(m.group(1))
        print('=== %s ===' % code)
        for k in sorted(data, key=lambda x: int(re.sub(r'\D', '', x) or 0)):
            if k == '__err':
                print('  ERR', data[k]); red.append('%s err' % code); continue
            rec = data[k]
            if mods and re.sub(r'\D', '', k) not in mods:
                continue
            done += 1
            lead, h3, h4 = rec.get('lead'), rec.get('h3'), rec.get('h4')
            def lhnum(x):
                try:
                    return round(float(x.replace('px', '')), 2)
                except Exception:
                    return None
            print('  %-6s lead=%s h3=%s h4=%s src=%s bodyLH=%s bold=%s tdBold=%s'
                  % (k,
                     ('%.2f' % lhnum(lead['lh'])) if lead else '—',
                     ('%.2f/%s' % (lhnum(h3['lh']) or -1, h3['color'])) if h3 else '—',
                     ('%.2f/%s' % (lhnum(h4['lh']) or -1, h4['color'])) if h4 else '—',
                     (rec['src'] or {}).get('color', '—'),
                     ('%.2f' % lhnum(rec['body']['lh'])) if rec.get('body') else '—',
                     rec.get('bold'), rec.get('tdBold')))
            # ---- 判据 ----
            if lead:
                if lhnum(lead['lh']) != lhnum(lead['fs']) * 2.02 and abs(lhnum(lead['lh']) / lhnum(lead['fs']) - 2.02) > 0.06:
                    red.append('%s %s 导语行高不是 2.02（%s / %s）' % (code, k, lead['lh'], lead['fs']))
                if '201, 162, 39' not in lead['bgl'] and lead['bgl'] not in ('rgb(201, 162, 39)',):
                    red.append('%s %s 导语左条不是金色（%s）' % (code, k, lead['bgl']))
            if h3:
                if '201, 162, 39' not in h3['bgl']:
                    red.append('%s %s h3 左条不是金色（%s）' % (code, k, h3['bgl']))
                if h3['bg'] in ('rgba(0, 0, 0, 0)', 'transparent'):
                    red.append('%s %s h3 没有底色' % (code, k))
            if h4:
                if '208, 32, 47' not in h4['bgl']:
                    red.append('%s %s h4 左条不是红色（%s）' % (code, k, h4['bgl']))
                if h4['bg'] in ('rgba(0, 0, 0, 0)', 'transparent'):
                    red.append('%s %s h4 没有底色' % (code, k))
            if rec.get('body'):
                if abs(lhnum(rec['body']['lh']) / lhnum(rec['body']['fs']) - 1.95) > 0.06:
                    red.append('%s %s 正文行高不是 1.95（%s / %s）' % (code, k, rec['body']['lh'], rec['body']['fs']))
                if rec['body']['color'] != 'rgb(94, 91, 82)':
                    red.append('%s %s 正文段落不是 #5e5b52（%s）' % (code, k, rec['body']['color']))
            if rec.get('src') and rec['src']['color'] != 'rgb(133, 133, 138)':
                red.append('%s %s 来源小字颜色被改了（%s）' % (code, k, rec['src']['color']))
            if rec.get('bold') not in (None, '500'):
                red.append('%s %s 段落粗体没降到 500（%s）' % (code, k, rec['bold']))
            if rec.get('tdBold') not in (None, '700', '900'):   # 900 = 表格里原有的合成粗体，与本次改动无关
                red.append('%s %s 表格粗体被动到了（%s）' % (code, k, rec['tdBold']))
            # ---- ⑥ 列表 / 解读块正文：必须与段落同为 #5e5b52 ----
            if rec.get('liColor') not in (None, 'rgb(94, 91, 82)'):
                red.append('%s %s 列表文字不是 #5e5b52（%s）' % (code, k, rec['liColor']))
            if rec.get('liBoldColor') not in (None, 'rgb(94, 91, 82)', 'rgb(208, 32, 47)'):
                red.append('%s %s 列表粗体颜色不对（%s）' % (code, k, rec['liBoldColor']))
            if rec.get('lvColor') not in (None, 'rgb(94, 91, 82)'):
                red.append('%s %s 解读块正文不是 #5e5b52（%s）' % (code, k, rec['lvColor']))
            # 反向守卫：结论块是参照版式，**不许**被这次改动联动（只报一次）
            if k == sorted(data, key=lambda x: int(re.sub(r'\D', '', x) or 0))[0] \
               and rec.get('verdictLiColor') not in (None, 'rgb(58, 56, 47)'):
                red.append('%s 核心结论块正文被联动改了（%s，应仍为 rgb(58, 56, 47)）'
                           % (code, rec['verdictLiColor']))
            # 对照组：表格 / 模块标题必须仍是深色（亮度低于 70），否则说明刷过头了
            for fld, label in (('tdColor', '表格单元格'), ('h2Color', '模块标题')):
                cv = rec.get(fld)
                if cv:
                    mm = re.match(r'rgb\((\d+),\s*(\d+),\s*(\d+)', cv)
                    if mm:
                        L = (int(mm.group(1)) * 299 + int(mm.group(2)) * 587 + int(mm.group(3)) * 114) // 1000
                        if L > 70:
                            red.append('%s %s %s 被刷浅了（%s）' % (code, k, label, cv))

    srv.shutdown()
    print()
    print('检查模块 %d 个 · 源 %s' % (done, src))
    if red:
        print('不合格 %d 项：' % len(red))
        for x in red:
            print('  ✗', x)
    else:
        print('全部通过 ✓')
    return 1 if red else 0


if __name__ == '__main__':
    sys.exit(main())
