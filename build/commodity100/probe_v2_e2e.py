#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""对比图页 v2 回归探针。

覆盖三件本次反馈的事：
  ① 工具栏「上传 / 管理 / 备份」三个按钮的**真实点击**
     （上次的 bug：函数都在，唯独忘了绑事件，点了没反应。上一版探针是直接调函数的，
       把这条路径绕过去了，所以没测出来 —— 这次一律用 .click()。）
  ② Excel 宽表（一列一个品种）**多列一次性批量导入**
  ③ 内置序列的编辑：改名 / 单位 / 颜色 / 复制为我的商品 / 恢复默认

跑法：
  /Users/luoshui/.workbuddy/binaries/python/envs/default/bin/python probe_v2_e2e.py
"""
import functools
import http.server
import io
import os
import re
import shutil
import socketserver
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
SRC_PAGE = os.path.join(ROOT, 'deliver', '大宗商品日线对比图-2005-2026.html')
SITE = os.path.join(HERE, '_probe_site')          # 独立临时目录：绝不碰 deploy_site/
PAGE = 'commodity-daily.html'
PROBE_PAGE = '_e2e_v2.html'
XLSX = os.path.join(SITE, '_v2_wide.xlsx')
PORT = 8794
EDGE = '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge'


# ---------------------------------------------------------------- 造测试用 xlsx
def make_xlsx():
    """宽表：第 1 行品种名、第 2 行单位、第 3 行起日期+数值。
    三列覆盖区间刻意不同（B 只到一半、C 只有后半段），另外加一列纯文本「备注」
    用来验证它不会被误当成数值列。"""
    import datetime
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = '指标数据'
    ws.append(['指标名称', '现货价:钼精矿:Mo:45%:河南', '市场价:钼铁:FeMo60:上海市',
               '市场价:钼铁:FeMo60:洛阳市:栾川', '备注'])
    ws.append(['单位', '元/吨', '元/吨', '元/吨', ''])
    base = datetime.date(2023, 1, 18)
    i = 0
    while i < 260:
        d = base + datetime.timedelta(days=i)
        i += 1
        if d.weekday() >= 5:          # 跳过周末，像真实交易日
            continue
        ws.append([
            d,
            round(5430 + i * 1.7, 1),
            round(341200 + i * 12.5, 1) if i < 160 else '',
            round(340700 + i * 11.1, 1) if i >= 90 else '',
            '现货报价' if i % 7 == 0 else '',
        ])
    for r in range(3, ws.max_row + 1):
        ws.cell(row=r, column=1).number_format = 'yyyy-mm-dd'
    wb.save(XLSX)
    return os.path.getsize(XLSX), ws.max_row


# ---------------------------------------------------------------- 探针脚本
DBG = r'''
<pre id="dbg" style="display:none"></pre>
<script>
(function(){
  var errs = [], out = [];
  window.addEventListener('error', function(e){ errs.push('ERR: ' + e.message); });
  window.addEventListener('unhandledrejection', function(e){
    errs.push('REJ: ' + ((e.reason && e.reason.message) || e.reason));
  });
  function log(k, v){ out.push(k + ' = ' + v); }
  /* 页面可能没有内置数据（build_opts.json → builtin:false）；内置相关用例据此跳过 */
  var HASB = (typeof HAS_BUILTIN === 'undefined') ? true : HAS_BUILTIN;
  function sec(t){ out.push(''); out.push('=== ' + t + ' ==='); }
  function txt(el){ return el ? (el.textContent || '').replace(/\s+/g, ' ').trim() : '(null)'; }
  function id(i){ return document.getElementById(i); }
  function isOpen(){ return id('mask').classList.contains('on'); }
  function title(){
    var h = document.querySelector('#dlg h3');
    return h ? h.textContent.replace(/\s+/g, ' ').trim() : '(无标题)';
  }
  function click(i){
    var e = id(i);
    if(!e){ out.push('✗ 找不到按钮 ' + i); return false; }
    e.click(); return true;
  }
  function waitFor(fn, ms, tag){
    return new Promise(function(res, rej){
      var t0 = Date.now();
      (function poll(){
        var v; try{ v = fn(); }catch(e){ return rej(new Error(tag + ' 抛错: ' + e.message)); }
        if(v) return res(v);
        if(Date.now() - t0 > (ms || 3000)) return rej(new Error(tag + ' 超时(' + (ms || 3000) + 'ms)'));
        requestAnimationFrame(poll);
      })();
    });
  }
  function sleep(ms){ return new Promise(function(r){ setTimeout(r, ms); }); }
  function post(){
    fetch('/__v2__', { method: 'POST',
      body: out.join('\n') + '\n\nJS错误: ' + (errs.length ? errs.join(' | ') : '无') });
  }

  (async function(){
    try{
      /* ---------------- 1. 工具栏三个按钮（真实点击） ---------------- */
      sec('1. 工具栏「我的商品」三个按钮（上次的 bug）');
      ['btn-up','btn-my','btn-bak'].forEach(function(i){ log('按钮存在 ' + i, !!id(i)); });

      click('btn-up');
      await waitFor(function(){ return isOpen() && !!id('fpick'); }, 1500, '点上传');
      log('点「⬆ 上传 Excel」', title());
      closeDlg();
      await waitFor(function(){ return !isOpen(); }, 800, '关闭上传');

      click('btn-my');
      await waitFor(function(){ return isOpen() && /管理/.test(title()); }, 1500, '点管理');
      log('点「☰ 管理」', title());
      closeDlg();
      await waitFor(function(){ return !isOpen(); }, 800, '关闭管理');

      click('btn-bak');
      await waitFor(function(){ return isOpen() && /备份/.test(title()); }, 1500, '点备份');
      log('点「⋯ 备份」', title());
      closeDlg();
      await waitFor(function(){ return !isOpen(); }, 800, '关闭备份');

      /* ---------------- 2. 多列批量导入 ---------------- */
      sec('2. Excel 宽表 → 多列一次性批量导入');
      click('btn-up');
      await waitFor(function(){ return !!id('fpick'); }, 1500, '上传面板');
      var ab = await (await fetch('_v2_wide.xlsx')).arrayBuffer();
      readUpFile(new File([ab], '钼系品种.xlsx'));
      await waitFor(function(){ return UP.list && UP.list.length; }, 8000, '解析 xlsx');

      log('工作表', UP.names.join(' / '));
      log('日期列 index', UP.map.dateCol);
      log('表头行 / 单位行 / 数据起始行', UP.map.hdrRow + ' / ' + UP.map.unitRow + ' / ' + UP.map.dataStart);
      log('识别到的数值列号', JSON.stringify(UP.map.valCols));
      log('默认已勾选列数', UP.pick.size);
      UP.list.forEach(function(it, k){
        log('  列' + it.c + ' [' + it.name + ']',
            (it.unit ? '单位' + it.unit + ' ' : '') + it.pts.length + ' 点  ' +
            (it.pts.length ? dayToStr(it.pts[0][0]) + '→' + dayToStr(it.pts[it.pts.length - 1][0]) : '—'));
      });
      log('汇总按钮文字', txt(id('up-ok')));
      log('统计条', txt(id('up-stat')).slice(0, 160));
      log('表头行是不是被当成数据（应无「2023-01-18」之类日期混进列名）',
          UP.list.every(function(it){ return !/^\d{4}-/.test(it.name); }));

      // 顺手改一个名称，验证手改能被采纳
      var firstCol = UP.list[0].c;
      var nmBox = document.querySelector('#up-rows [data-nm="' + firstCol + '"]');
      nmBox.value = '钼精矿·改过名';
      nmBox.dispatchEvent(new Event('input', { bubbles: true }));
      await waitFor(function(){ return txt(id('up-stat')).indexOf('改过名') >= 0; }, 800, '名称写回');

      var before = CUSTOM.length;
      id('up-ok').click();
      await waitFor(function(){ return CUSTOM.length > before; }, 2500, '批量导入');
      log('导入前/后 CUSTOM 条数', before + ' → ' + CUSTOM.length);
      log('本次导入的名称', CUSTOM.slice(before).map(function(s){ return s.n; }).join(' / '));
      log('本次导入的点数', CUSTOM.slice(before).map(function(s){
        return s.n + ':' + s.pts.length; }).join(' / '));
      log('单位是否自动带过来', CUSTOM.slice(before).map(function(s){
        return s.n + '[' + (s.u || '空') + ']'; }).join(' / '));
      log('颜色互不重复', (function(){
        var cs = CUSTOM.slice(before).map(function(s){ return String(s.col).toLowerCase(); });
        return new Set(cs).size === cs.length;
      })());
      log('图里已出现（active 命中）', CUSTOM.slice(before).every(function(s){
        return state.active.has(s.c) && chart.data.datasets.some(function(d){ return d._c === s.c; }); }));

      /* 顺带确认：自定义 chip 的 ✎ 仍然进「改数据」面板，没被内置编辑面板顶掉 */
      var uChip = document.querySelector('.chip[data-c="' + CUSTOM[before].c + '"]');
      log('自定义 chip 带 ✎', !!uChip.querySelector('.ed'));
      uChip.querySelector('.ed').click();
      await waitFor(function(){ return !!id('ed-name') || !!document.querySelector('#dlg input[data-f="v"]'); },
                   1500, '自定义编辑面板');
      log('点自定义 ✎ → 面板', title());
      log('有逐点编辑表', !!document.querySelector('#dlg input[data-f="v"]'));
      closeDlg();
      await waitFor(function(){ return !isOpen(); }, 800, '关闭');

      /* ---------------- 3. 内置序列编辑 ---------------- */
      if(!HASB){
        sec('3. 内置序列可编辑');
        log('内置序列编辑', '⊘ 本页无内置数据，跳过');
      }else{
      sec('3. 内置序列可编辑');
      var g0 = BYCODE['gold'];
      log('gold 原始名 / 原始色', g0.n0 + ' / ' + g0.col0);
      var gc = document.querySelector('.chip[data-c="gold"]');
      log('内置 chip 带 ✎', !!(gc && gc.querySelector('.ed')));
      gc.querySelector('.ed').click();
      await waitFor(function(){ return !!id('eb-name'); }, 1500, '内置编辑面板');
      log('面板标题', title());
      log('面板里显示的原始名称', txt(document.querySelector('#dlg .kvs')));

      id('eb-name').value = '黄金·改名验证';
      id('eb-unit').value = '美元/盎司';
      id('eb-col').value = '#00e0b8';
      click('eb-save');
      await waitFor(function(){ return !isOpen(); }, 1500, '保存并关闭');
      log('保存后 BYCODE.gold.n / u / col', BYCODE['gold'].n + ' / ' + BYCODE['gold'].u + ' / ' + BYCODE['gold'].col);
      log('BOVER 记录', JSON.stringify(BOVER['gold'] || null));
      log('localStorage 已写入', !!localStorage.getItem('wb_c100_bover_v1'));
      var gc2 = document.querySelector('.chip[data-c="gold"]');
      log('chip 文字已更新', gc2.textContent.indexOf('黄金·改名验证') >= 0);
      log('chip 出现「已改过」小标记', !!gc2.querySelector('.ovr'));
      var gds = chart.data.datasets.filter(function(d){ return d._c === 'gold'; })[0];
      log('图表 dataset 标签 / 颜色', gds ? (gds.label + ' / ' + gds.borderColor) : '(不在图里)');

      // 复制为我的商品
      document.querySelector('.chip[data-c="gold"] .ed').click();
      await waitFor(function(){ return !!id('eb-copy'); }, 1500, '再开面板');
      var cb = CUSTOM.length;
      click('eb-copy');
      await waitFor(function(){ return CUSTOM.length > cb; }, 3000, '复制');
      log('复制后 CUSTOM 条数', cb + ' → ' + CUSTOM.length);
      log('复制后打开了数据编辑面板', title());
      log('副本点数（应与内置 gold 相同）', BYCODE[CUSTOM[CUSTOM.length - 1].c].pts.length + ' vs ' + BYCODE['gold'].pts.length);
      log('副本可改数据点（有逐点表格）', !!document.querySelector('#dlg input[data-f="v"]'));
      closeDlg();
      await waitFor(function(){ return !isOpen(); }, 800, '关闭');

      // 恢复默认
      document.querySelector('.chip[data-c="gold"] .ed').click();
      await waitFor(function(){ return !!id('eb-reset'); }, 1500, '三开面板');
      var rstDisabled = id('eb-reset').disabled;
      log('「恢复默认」按钮可用（改过之后应为 false）', rstDisabled);
      click('eb-reset');
      await waitFor(function(){ return !isOpen(); }, 1500, '恢复默认');
      log('恢复后 name / unit / col', BYCODE['gold'].n + ' / ' + BYCODE['gold'].u + ' / ' + BYCODE['gold'].col);
      log('BOVER 已清空', JSON.stringify(BOVER['gold'] || null));
      log('chip 回到原名', document.querySelector('.chip[data-c="gold"]').textContent.indexOf(g0.n0) >= 0);
      }

      /* ---------------- 4. 清理 ---------------- */
      sec('4. 清理探针产生的数据');
      var drop = CUSTOM.filter(function(s){
        return s.n.indexOf('钼') >= 0 || s.n.indexOf('副本') >= 0;
      });
      log('清掉的条数', drop.length);
      /* ★ 必须显式调 cloudDel：以前这里只把 CUSTOM 数组裁掉、没通知云端，
         结果每跑一次探针就往 wb_c100_series 里留一批垃圾记录。 */
      drop.forEach(function(s){ cloudDel(s.c, true); });
      CUSTOM = CUSTOM.filter(function(s){ return drop.indexOf(s) < 0; });
      afterCustomChange();
      log('剩余 CUSTOM', CUSTOM.length);
      log('剩余 BOVER', JSON.stringify(BOVER));
      log('页头点数', txt(id('ptn')));

      await sleep(3500);           // 等云端的软删 PATCH 真发出去，再回传结果
      if(!WBCloud.off()){
        var rr = await WBCloud.list();
        var still = (rr || []).filter(function(r){
          return !r.is_del && drop.some(function(s){ return s.c === r.id; });
        });
        log('云端复核：仍未软删的条数（应 0）', still.length);
      } else log('云端复核', '本机模式（探针已屏蔽云端写入），无需清理云端');
      post();
    }catch(e){
      out.push('');
      out.push('✗✗ 探针中断: ' + ((e && e.message) || e));
      out.push((e && e.stack) ? String(e.stack).split('\n').slice(0, 4).join('\n') : '');
      post();
    }
  })();
})();
</script>
'''


# ---------------------------------------------------------------- 第二段：刷新持久化
PRE_BOVER = ('<script>try{localStorage.setItem("wb_c100_bover_v1",JSON.stringify('
             '{gold:{n:"持久化验证·金",u:"美元/盎司",col:"#00b8ff"}}))}catch(e){}</script>')

DBG2 = r'''
<pre id="dbg" style="display:none"></pre>
<script>
(function(){
  var errs = [], out = [];
  window.addEventListener('error', function(e){ errs.push('ERR: ' + e.message); });
  function log(k, v){ out.push(k + ' = ' + v); }
  function post(){ fetch('/__v2__', { method: 'POST',
    body: out.join('\n') + '\n\nJS错误: ' + (errs.length ? errs.join(' | ') : '无') }); }
  setTimeout(function(){
    try{
      out.push('');
      out.push('=== 5. 刷新后内置改动是否还在（本机持久化） ===');
      if(typeof HAS_BUILTIN !== 'undefined' && !HAS_BUILTIN){
        log('内置改动持久化', '⊘ 本页无内置数据，跳过');
        localStorage.removeItem('wb_c100_bover_v1');
        throw { skip: true };
      }
      var g = BYCODE['gold'];
      log('BYCODE.gold.n / u / col', g.n + ' / ' + g.u + ' / ' + g.col);
      log('BOVER 从 localStorage 读回', JSON.stringify(BOVER['gold'] || null));
      var chip = document.querySelector('.chip[data-c="gold"]');
      log('chip 文字', chip ? chip.textContent.replace(/\s+/g, ' ').trim() : '(无)');
      var ds = chart.data.datasets.filter(function(d){ return d._c === 'gold'; })[0];
      log('图表 dataset 标签 / 颜色', ds ? (ds.label + ' / ' + ds.borderColor) : '(不在图里)');
      localStorage.removeItem('wb_c100_bover_v1');
      log('已清理本机覆盖层（避免污染后续运行）', !localStorage.getItem('wb_c100_bover_v1'));
    }catch(e){
      if(!(e && e.skip)) out.push('✗ ' + (e && e.message || e));
    }
    post();
  }, 900);
})();
</script>
'''


# ---------------------------------------------------------------- 跑浏览器
RESULT = []


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        n = int(self.headers.get('Content-Length') or 0)
        RESULT.append(self.rfile.read(n).decode('utf-8', 'ignore'))
        self.send_response(200)
        self.send_header('Content-Length', '2')
        self.end_headers()
        self.wfile.write(b'ok')


def serve():
    h = functools.partial(Quiet, directory=SITE)
    socketserver.TCPServer.allow_reuse_address = True
    httpd = socketserver.TCPServer(('127.0.0.1', PORT), h)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def run_probe(url, timeout=180):
    """跑一次无头浏览器，等页内探针把结果 POST 回来（真实等待，不用虚拟时间）。"""
    del RESULT[:]
    cmd = [EDGE, '--headless=new', '--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage',
           '--window-size=1512,1600', url]
    p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    t0 = time.time()
    while time.time() - t0 < timeout:
        if RESULT:
            break
        time.sleep(0.25)
    time.sleep(0.4)
    try:
        p.terminate(); p.wait(timeout=8)
    except Exception:
        try: p.kill()
        except Exception: pass
    if RESULT:
        return RESULT[0]
    return '（%.0f 秒内没收到探针回传 —— 页面可能在早期就抛错了）' % timeout


def main():
    shutil.rmtree(SITE, ignore_errors=True)
    os.makedirs(SITE, exist_ok=True)
    size, rows = make_xlsx()
    print('测试用 xlsx：%s（%d 字节 · %d 行）' % (os.path.basename(XLSX), size, rows))
    src = io.open(SRC_PAGE, encoding='utf-8').read()
    # ★ 探针只测 UI 行为，不该往生产表 wb_c100_series 里写东西 ——
    #   把注入的云端配置掏空，WBCloud.off() 即为 true，全部读写退回本机。
    #   （以前没掏空，每跑一次就往云端留 4 条垃圾记录，还得手工清。）
    src, n0 = re.subn(r'window\.WB_CFG\s*=\s*\{[^}]*\};',
                      'window.WB_CFG = { envId: "", key: "", rest: "" };', src, count=1)
    print('云端写入：已屏蔽（%d 处配置置空）→ 本机模式' % n0)
    io.open(os.path.join(SITE, PAGE), 'w', encoding='utf-8').write(src)
    io.open(os.path.join(SITE, PROBE_PAGE), 'w', encoding='utf-8').write(
        src.replace('</body>', DBG + '</body>', 1))
    # 第二段：进页面之前就把覆盖层写进 localStorage，验证「刷新后改动还在」
    i = src.find('<body')
    j = src.find('>', i)
    page2 = src[:j + 1] + PRE_BOVER + src[j + 1:]
    io.open(os.path.join(SITE, '_e2e_v2b.html'), 'w', encoding='utf-8').write(
        page2.replace('</body>', DBG2 + '</body>', 1))
    srv = serve()
    print('\n' + '=' * 74)
    print(run_probe('http://localhost:%d/%s' % (PORT, PROBE_PAGE)))
    print('=' * 74)
    print(run_probe('http://localhost:%d/_e2e_v2b.html' % PORT, timeout=90))
    print('=' * 74)
    srv.shutdown()
    shutil.rmtree(SITE, ignore_errors=True)
    print('\n（已清理探针临时目录 %s）' % os.path.relpath(SITE, HERE))
    return 0


if __name__ == '__main__':
    sys.exit(main())
