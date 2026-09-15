# -*- coding: utf-8 -*-
"""表格「增加行 / 删除行」端到端验收（真机 Edge + 真云端研报）。

用户诉求：「模块的表格和 图表的表格都增加一个删除行和增加行的功能」。

两处表格的实现完全不同，所以分开盯：

  A. 图表数据表（管理面板 →「图表」）
     `#c-grid` 里的 `.rpt-grid`，单元格是带 data-r/data-c 的 input。
     增删行 = readGrid() 拿到当前值 → 改 model → gridPaint() 重画。
     ⚠️ 关键风险：重画会不会把手改的内容冲掉？→ 专门有一条断言。

  B. 模块正文表格（管理面板 →「模块」→ 富文本编辑区里的 <table>）
     光标在哪个 tr 里，就在那儿增删。用的是真选区 + DOM 增删，
     ⚠️ 关键风险：改完没置 UI.rteDirty → 保存时被静默丢弃 → 也专门有断言。

共同点：**两处都只改编辑框、不写数据库**（写库仍然只走「保存」按钮）。
本探针**从不点保存** → 不写库、不动用户真实研报数据。

另外验门禁：删行按「删除」计、被 RGATE 包住；不带哨兵时必须弹密码框且**行数不变**
（证明门禁不是装饰），带哨兵（真实校验通过后的路径）才直通；插行不验密码。
"""
import html
import http.server
import json
import os
import re
import socketserver
import subprocess
import threading

BASE = r'C:\Users\50522\WorkBuddy\2026-09-10-14-50-38'
SRC = os.path.join(BASE, 'deploy', 'report.html')
OUT = os.path.join(BASE, 'build', '_probe_tablerows.html')
PORT = 8920
CODE = '600456'

PROBE = '''
<div id="probeOut" style="display:none"></div>
<script>
(function(){
  var R = window.__R;
  function out(){
    document.getElementById('probeOut').textContent = 'PROBE_JSON:' + JSON.stringify(R);
  }
  /* ---------- 取值工具 ---------- */
  function gridRows(){
    var trs = document.querySelectorAll('#c-grid .rpt-grid tbody tr'), o = [];
    for(var i = 0; i < trs.length; i++){
      var ins = trs[i].querySelectorAll('input'), r = [];
      for(var j = 0; j < ins.length; j++) r.push(ins[j].value);
      o.push(r);
    }
    return o;
  }
  function gridHead(){
    /* ⚠️ 第 1 个 th 是写死的行号列「#」，不是数据列，必须跳过 */
    var ths = document.querySelectorAll('#c-grid .rpt-grid thead th'), o = [];
    for(var i = 1; i < ths.length; i++) o.push(String(ths[i].textContent || '').trim());
    return o;
  }
  function ixNumbers(){
    /* 行号 = td.ix 的第一个文本节点（后面还跟着一个 ✕ 按钮） */
    var tds = document.querySelectorAll('#c-grid .rpt-grid tbody tr td.ix'), o = [];
    for(var i = 0; i < tds.length; i++){
      var n = tds[i].childNodes[0];
      o.push(String((n && n.nodeValue) || '').trim());
    }
    return o;
  }
  function gxCount(){ return document.querySelectorAll('#c-grid .rpt-grid tbody tr td.ix .gx').length; }
  function info(){ return String((($('c-gridinfo') || {}).textContent) || '').trim(); }
  function json(){ return JSON.parse(($('c-json') || {}).value || '{}'); }
  function toastText(){ return String((($('rptToast') || {}).textContent) || '').slice(0, 140); }
  function modalOn(){ return $('rptPMask').className.indexOf('on') >= 0; }
  function btnCount(needle){
    var els = document.querySelectorAll('.rpt-iotools button, .rtebar button'), n = 0;
    for(var i = 0; i < els.length; i++){
      var oc = els[i].getAttribute('onclick') || '';
      if(oc.indexOf(needle) >= 0) n++;
    }
    return n;
  }
  function btnNoBlur(needle){
    var els = document.querySelectorAll('.rtebar button'), n = 0;
    for(var i = 0; i < els.length; i++){
      var oc = els[i].getAttribute('onclick') || '';
      if(oc.indexOf(needle) >= 0 && /return false/.test(els[i].getAttribute('onmousedown') || '')) n++;
    }
    return n;
  }
  /* ---------- 富文本区工具 ---------- */
  /* 取编辑区里**最后一张**表格：B1 会在模块末尾补一张「带表头」的标准表格，
     所以最后一张才是本轮要操作的对象（原表有没有 thead 不影响断言口径）。 */
  function rteTable(){
    var ts = document.querySelectorAll('#m-edit table');
    return ts.length ? ts[ts.length - 1] : null;
  }
  function rteTrs(){ var t = rteTable(); return t ? t.getElementsByTagName('tr') : []; }
  function rteBody(){ var t = rteTable(); return (t && t.getElementsByTagName('tbody')[0]) || null; }
  function rteBodyTrs(){ var b = rteBody(); return b ? b.getElementsByTagName('tr') : []; }
  function rteHeadTr(){
    var t = rteTable(); if(!t) return null;
    var h = t.getElementsByTagName('thead')[0];
    return h ? h.getElementsByTagName('tr')[0] : null;
  }
  function caretInto(el){
    var r = document.createRange();
    r.selectNodeContents(el); r.collapse(true);
    var s = getSelection(); s.removeAllRanges(); s.addRange(r);
  }
  function styleOf(el){ return String((el && el.getAttribute && el.getAttribute('style')) || ''); }
  /* 「真的会存下去吗」的证据：rteRead 是保存时真正会写库的那段 HTML。
     ⚠️ 两个坑（都实踩过）：
       ① rteRead(id, orig) 在 UI.rteDirty 没置位时返回的是**传进去的 orig**，不是 DOM ——
          所以计数前必须把模块原始 html 当 orig 传进去，否则「改动前」会读到 0（第一版就栽在这）。
       ② 它包含**整个模块**（可能有多张表）→ 只能拿「改动前后自己的差值」比，
          别去和「某一张表的行数」比（那是不相干的两个数）。
       ③ 库里的大小写不保证 → 统一转小写再数。 */
  function htmlTrs(){
    var orig = (Rpt.findMod(R.modId) || {}).html || '';
    return String(rteRead('m-edit', orig)).toLowerCase().split('<tr').length - 1;
  }

  var steps = [], si = 0;
  function step(name, fn){ steps.push({n:name, f:fn}); }

  /* ================================ A. 图表数据表 ================================ */
  step('A1 打开图表数据表：工具条 / 行内 ✕ / 门禁标记', function(){
    R.passOk = (typeof RPASS_OK === 'object');
    R.chartKeys = St.chartKeys.length;
    var keys = St.chartKeys.filter(function(k){
      var o = (St.charts[k] || {}).opt || {}, s0 = (o.series || [])[0] || {};
      return s0.type !== 'pie';
    });
    R.pieKey = '';
    for(var i = 0; i < St.chartKeys.length; i++){
      var o = (St.charts[St.chartKeys[i]] || {}).opt || {}, s0 = (o.series || [])[0] || {};
      if(s0.type === 'pie'){ R.pieKey = St.chartKeys[i]; break; }
    }
    R.selKey = keys[0];
    if(!keys.length) keys = St.chartKeys.slice(0, 1);     /* 全是饼图时的兜底 */
    Rpt.openChart(keys[0]);
    R.selKey = keys[0];
    R.tools = !!document.querySelector('.rpt-iotools');
    R.btnAdd = btnCount('gridAddRow');
    R.btnDel = btnCount('gridDelFocus');
    R.head0 = gridHead();
    R.n0 = gridRows().length;
    R.info0 = info();
    R.gx0 = gxCount();
    R.gateGrid = {gated:Rpt.gridDelRow.__gated === true, act:Rpt.gridDelRow.__act,
                  danger:Rpt.gridDelRow.__danger, addGated:!!Rpt.gridAddRow.__gated,
                  focusGated:!!Rpt.gridDelFocus.__gated};
  });

  step('A2 不带哨兵删行 → 必须弹密码框且行数不变（门禁不是装饰）', function(){
    try{ sessionStorage.removeItem('rpt_pass_fresh_v1'); }catch(e){}
    R.nGateBefore = gridRows().length;
    Rpt.gridDelRow(0);                       /* 故意不带哨兵 */
    R.gateModal = modalOn();
    R.gateHeld = (gridRows().length === R.nGateBefore);
    Rpt.cancelPass();
    R.gateModalClosed = !modalOn();
  });

  step('A3 ＋ 增加行：末行变空、行号/✕/计数同步、表头与系列数不变', function(){
    Rpt.gridAddRow();                        /* 未挂门禁 → 不需要哨兵 */
    R.n1 = gridRows().length;
    R.info1 = info();
    R.head1 = gridHead();
    R.rows1 = gridRows();
    R.last1 = R.rows1[R.rows1.length - 1];
    R.ix1 = ixNumbers();
    R.gx1 = gxCount();
    R.addToast = toastText();
  });

  step('A4 手改一格后再加行：手改不能丢（重画必须保数据）', function(){
    var inp = document.querySelector('#c-grid .rpt-grid input[data-r="0"][data-c="1"]');
    inp.value = '999.5';
    Rpt.gridAddRow();
    var again = document.querySelector('#c-grid .rpt-grid input[data-r="0"][data-c="1"]');
    R.keptVal = again ? again.value : 'missing';
    R.n2 = gridRows().length;
  });

  step('A5 删指定行（✕ 的路径）：删的是那一行、序号重排', function(){
    var before = gridRows();
    R.mid = before[1].slice();
    R.beforeN = before.length;
    Rpt.gridDelRow(1, RPASS_OK);             /* 哨兵 = 真实校验通过后的路径 */
    var after = gridRows();
    R.n3 = after.length;
    R.shiftOk = (JSON.stringify(after[1]) === JSON.stringify(before[2]));
    R.kept0 = after[0];
    R.ix3 = ixNumbers();
    R.info3 = info();
    R.delToast = toastText();
  });

  step('A6 增删后的表格保存时会写成什么（applyGrid 干跑，不落库）', function(){
    var rows = readGrid().rows;
    var o2 = applyGrid(JSON.parse(JSON.stringify(json())), readGrid());
    var xa2 = Array.isArray(o2.xAxis) ? o2.xAxis[0] : o2.xAxis;
    R.jsonRows = rows.length;
    R.catsAfter = ((xa2 && xa2.data) || []).length;
    R.dataAfter = ((o2.series[0] || {}).data || []).length;
    R.lastDataVal = ((o2.series[0] || {}).data || [])[rows.length - 1];
    R.headUnchanged = (JSON.stringify(gridHead()) === JSON.stringify(R.head0));
  });

  step('A7 工具栏「－ 删除行」没点进格子 → 删最后一行', function(){
    var gated = Rpt.gridDelRow, raw = gated.__raw, rec = null;
    Rpt.gridDelRow = function(i){ rec = i; return raw.call(Rpt, i, RPASS_OK); };
    R.activeR0 = (document.activeElement && document.activeElement.getAttribute)
                 ? document.activeElement.getAttribute('data-r') : null;
    var before = gridRows();
    Rpt.gridDelFocus();
    Rpt.gridDelRow = gated;                  /* 恢复带门禁的包装版 */
    R.focusIdxNoCell = rec;
    R.n4 = gridRows().length;
    R.lastGone = (JSON.stringify(gridRows()[gridRows().length - 1]) === JSON.stringify(before[before.length - 2]));
  });

  step('A8 工具栏「－ 删除行」点进第 1 行 → 删第 1 行（真 focus）', function(){
    var inp = document.querySelector('#c-grid .rpt-grid input[data-r="0"]');
    try{ inp.focus(); }catch(e){}
    var ae = document.activeElement;
    R.realActiveR = (ae && ae.getAttribute) ? ae.getAttribute('data-r') : 'no-ae';
    var before = gridRows();
    var gated = Rpt.gridDelRow, raw = gated.__raw, rec = null;
    Rpt.gridDelRow = function(i){ rec = i; return raw.call(Rpt, i, RPASS_OK); };
    Rpt.gridDelFocus();
    Rpt.gridDelRow = gated;
    R.focusIdxCell = rec;
    R.n5 = gridRows().length;
    R.firstNow = gridRows()[0];
    R.firstWant = before[1];
    R.firstVanish = (JSON.stringify(before[0]) !== JSON.stringify(gridRows()[0]));
  });

  step('A9 gridDelFocus 的取行逻辑（遮蔽 activeElement，确定性验证）', function(){
    var fake = {getAttribute:function(n){ return n === 'data-r' ? '1' : null; }};
    var had = Object.getOwnPropertyDescriptor(document, 'activeElement');
    Object.defineProperty(document, 'activeElement', {configurable:true, get:function(){ return fake; }});
    var before = gridRows();
    var gated = Rpt.gridDelRow, raw = gated.__raw, rec = null;
    Rpt.gridDelRow = function(i){ rec = i; return raw.call(Rpt, i, RPASS_OK); };
    Rpt.gridDelFocus();
    Rpt.gridDelRow = gated;
    if(had) Object.defineProperty(document, 'activeElement', had); else delete document.activeElement;
    R.shadowIdx = rec;
    R.shadowRemoved = (JSON.stringify(before[1]) !== JSON.stringify(gridRows()[1]));
    R.n6 = gridRows().length;
  });

  step('A10 只剩 1 行时拒绝删除（不能把表删空）', function(){
    var guard = 0;
    while(gridRows().length > 1 && guard++ < 40) Rpt.gridDelRow(0, RPASS_OK);
    R.oneRow = gridRows().length;
    var before = gridRows();
    Rpt.gridDelRow(0, RPASS_OK);
    R.refuseHeld = (JSON.stringify(before) === JSON.stringify(gridRows()));
    R.refuseToast = toastText();
    Rpt.gridAddRow(); Rpt.gridAddRow(); Rpt.gridAddRow();
    R.n7 = gridRows().length;
  });

  step('A11 饼图也能增删行，且空行不会变成 0 号扇区', function(){
    if(!R.pieKey){ R.pieSkipped = true; return; }
    Rpt.openChart(R.pieKey);
    R.pieN0 = gridRows().length;
    R.pieHead = gridHead();
    Rpt.gridAddRow();
    R.pieN1 = gridRows().length;
    R.pieLastEmpty = (JSON.stringify(gridRows()[gridRows().length - 1]) === JSON.stringify(['', '']));
    var o = applyGrid(json(), readGrid());
    R.pieSaved = ((o.series[0] || {}).data || []).length;
    Rpt.gridDelRow(gridRows().length - 1, RPASS_OK);
    R.pieN2 = gridRows().length;
    Rpt.openChart(R.selKey);                 /* 回到非饼图那张，便于截图/留证 */
  });

  /* ================================ B. 模块正文表格 ================================ */
  step('B1 打开含表格的模块：工具条出现「＋ 行 / － 行」', function(){
    var pick = null;
    for(var i = 0; i < St.mods.length; i++){
      if(String(St.mods[i].html || '').indexOf('<table') >= 0){ pick = St.mods[i]; break; }
    }
    R.tableSrc = pick ? 'cloud' : 'synthetic';
    if(!pick) pick = St.mods[0];
    /* 原表没有 <thead> 就再补一张带表头的标准表格（只改内存、不落库）——
       保证「光标在表头里插行 / 表头行不能删」这两条也被真正跑到。
       注意 rteTable() 取的是最后一张，所以补的表就是被测对象。 */
    if(!/<thead/i.test(String(pick.html || ''))){
      /* 故意给表头红底、正文白底 —— 这样「插行时抄的是正文行样式、没把表头红底带下来」
         才是一条**有意义**的断言（全空样式的话它恒真，测了等于没测）。 */
      pick.html = String(pick.html || '') +
        '<table><thead><tr>' +
        '<th style="background:#c8102e;color:#fff">列A</th>' +
        '<th style="background:#c8102e;color:#fff">列B</th></tr></thead><tbody>' +
        '<tr><td style="padding:8px">a1</td><td style="padding:8px">b1</td></tr>' +
        '<tr><td style="padding:8px">a2</td><td style="padding:8px">b2</td></tr>' +
        '<tr><td style="padding:8px">a3</td><td style="padding:8px">b3</td></tr></tbody></table>';
      R.tableSrc = R.tableSrc + '+appended';
    }
    R.modId = pick.id; R.modNo = String(pick.no || '');
    Rpt.openMod(pick.id);
    R.rteHasTable = !!rteTable();
    R.usedThead = !!rteHeadTr();
    R.trs0 = rteTrs().length;
    R.bodyTrs0 = rteBodyTrs().length;
    R.rteAddBtn = btnCount("rteRow('m-edit',1)");
    R.rteDelBtn = btnCount("rteRow('m-edit',-1)");
    R.rteNoBlur = [btnNoBlur("rteRow('m-edit',1)"), btnNoBlur("rteRow('m-edit',-1)")];
    R.gateRte = {gated:Rpt.rteRow.__gated === true, act:Rpt.rteRow.__act, danger:Rpt.rteRow.__danger};
  });

  step('B2 光标在第 2 行 → ＋ 行插在下面，样式照抄、置位 dirty、光标落进新行', function(){
    UI.rteDirty['m-edit'] = 0;
    var trs = rteTrs();
    var target = trs[1];
    R.targetIsSecond = !!target;
    var ncell = target.cells.length;
    var donorStyle = styleOf(target.cells[0]);
    caretInto(target.cells[0]);
    R.caretFound = (rteRowAt('m-edit') === target);
    R.readBackTrs0 = htmlTrs();
    Rpt.rteRow('m-edit', 1, RPASS_OK);
    var trs2 = rteTrs();
    R.trAfter = trs2.length;
    R.newIdx = 2;
    R.newCells = trs2[2].cells.length;
    R.ncell = ncell;
    R.styleCopied = (styleOf(trs2[2].cells[0]) === donorStyle);
    R.newEmpty = (String(trs2[2].cells[0].textContent || '').replace(String.fromCharCode(160), '').length === 0);
    R.dirty1 = UI.rteDirty['m-edit'];
    R.caretInNew = (rteRowAt('m-edit') === trs2[2]);
    R.newIsTd = (trs2[2].cells[0].nodeName === 'TD');
    R.readBackTrs = htmlTrs();
    R.addToastRte = toastText();
  });

  step('B3 光标在表头 → 新行插进 tbody 第一行（不出现两行表头）', function(){
    var t = rteTable();
    if(!t || !t.getElementsByTagName('thead')[0]){ R.theadSkipped = true; return; }
    var headTr = t.getElementsByTagName('thead')[0].getElementsByTagName('tr')[0];
    var thStyle = styleOf(headTr.cells[0]);
    var bodyStyle0 = styleOf(rteBodyTrs()[0].cells[0]);
    R.theadRows0 = t.getElementsByTagName('thead')[0].getElementsByTagName('tr').length;
    R.tbodyRows0 = rteBodyTrs().length;
    caretInto(headTr.cells[0]);
    Rpt.rteRow('m-edit', 1, RPASS_OK);
    var t2 = rteTable();
    R.theadRows1 = t2.getElementsByTagName('thead')[0].getElementsByTagName('tr').length;
    R.tbodyRows1 = rteBodyTrs().length;
    R.headNewIsTd = (rteBodyTrs()[0].cells[0].nodeName === 'TD');
    R.headNewStyle = styleOf(rteBodyTrs()[0].cells[0]);
    R.thStyle = thStyle; R.bodyStyle0 = bodyStyle0;
    R.headStyleOk = (styleOf(rteBodyTrs()[0].cells[0]) !== thStyle);
  });

  step('B4 表头行删不掉（拒绝 + 提示）', function(){
    var t = rteTable();
    if(!t || !t.getElementsByTagName('thead')[0]){ R.theadSkippedB4 = true; return; }
    var headTr = t.getElementsByTagName('thead')[0].getElementsByTagName('tr')[0];
    caretInto(headTr.cells[0]);
    var n0 = rteTrs().length;
    Rpt.rteRow('m-edit', -1, RPASS_OK);
    R.headRefuse = (rteTrs().length === n0);
    R.headRefuseToast = toastText();
    R.headStillThere = (rteTable().getElementsByTagName('thead')[0].getElementsByTagName('tr').length === 1);
  });

  step('B5 － 行 删掉光标所在行（DOM 里那一行真的没了）', function(){
    var victim = rteBodyTrs()[1];
    R.victimOk = !!victim;
    var n0 = rteBodyTrs().length;
    caretInto(victim.cells[0]);
    R.readBackTrs2a = htmlTrs();
    Rpt.rteRow('m-edit', -1, RPASS_OK);
    R.bodyAfter = rteBodyTrs().length;
    R.bodyWant = n0 - 1;
    R.domTrsAfterDel = rteTrs().length;
    R.victimGone = !document.contains(victim);
    R.dirty2 = UI.rteDirty['m-edit'];
    R.readBackTrs2 = htmlTrs();
    R.delToastRte = toastText();
  });

  step('B6 删到只剩一行 → 再删被拒', function(){
    var guard = 0;
    while(rteBodyTrs().length > 1 && guard++ < 40){
      caretInto(rteBodyTrs()[0].cells[0]);
      Rpt.rteRow('m-edit', -1, RPASS_OK);
    }
    R.oneBodyRow = rteBodyTrs().length;
    caretInto(rteBodyTrs()[0].cells[0]);
    var before = rteTrs().length;
    Rpt.rteRow('m-edit', -1, RPASS_OK);
    R.lastRefuse = (rteTrs().length === before);
    R.lastRefuseToast = toastText();
  });

  step('B7 光标不在表格里 → 只提示、不动 DOM', function(){
    var box = $('m-edit');
    var r = document.createRange();
    r.selectNodeContents(box); r.collapse(true);
    var s = getSelection(); s.removeAllRanges(); s.addRange(r);
    R.outOfTable = (rteRowAt('m-edit') === null);
    var n0 = rteTrs().length;
    Rpt.rteRow('m-edit', 1, RPASS_OK);
    Rpt.rteRow('m-edit', -1, RPASS_OK);
    R.outHeld = (rteTrs().length === n0);
    R.outToast = toastText();
  });

  step('B8 不带哨兵删行 → 弹密码框且行数不变；插行不弹框（直通）', function(){
    try{ sessionStorage.removeItem('rpt_pass_fresh_v1'); }catch(e){}
    caretInto(rteBodyTrs()[0].cells[0]);
    Rpt.rteRow('m-edit', 1, RPASS_OK);
    Rpt.rteRow('m-edit', 1, RPASS_OK);
    var before = rteTrs().length;
    caretInto(rteBodyTrs()[0].cells[0]);
    Rpt.rteRow('m-edit', -1);                      /* 不带哨兵 */
    R.rteModal = modalOn();
    R.rteHeld = (rteTrs().length === before);
    Rpt.cancelPass();
    caretInto(rteBodyTrs()[0].cells[0]);
    Rpt.rteRow('m-edit', 1);                       /* 插行：when 分支 → 直通 */
    R.rteNoModalForAdd = !modalOn();
    R.rteAddedNoTick = (rteTrs().length === before + 1);
  });

  step('B9 留证：两处表格的最终状态 + 页面无错', function(){
    R.gridMountedNow = !!$('c-grid');       /* 现在停在「模块」页，图表那条表已经不在 DOM 里了 */
    R.gridLastInfo = R.info3;               /* 图表表的最后状态（A5 之后） */
    R.gridLastRows = R.n7;                  /* A10 补回到的行数 */
    R.finalRteTrs = rteTrs().length;
    R.finalRteCells = rteTrs().length ? rteTrs()[0].cells.length : 0;
    R.finalDirty = UI.rteDirty['m-edit'];
    R.pageErrs = (window.__RPT_ERR || []).slice(0, 5);
    R.echartsUp = (typeof echarts !== 'undefined');
    R.chartsRendered = document.querySelectorAll('canvas').length;
  });

  /* 页面 boot 是异步的（要从云端把整份研报拉回来）→ 等 St.chartKeys 出现再开跑。
     所有步骤都是同步的（没有 FileReader / DecompressionStream 那种跨线程回调），
     所以这里是一路直跑，不依赖定时器推进 —— 也就不会踩「虚拟时间饿死回调」的坑。 */
  var boot = 0;
  (function waitBoot(){
    boot++;
    R.bootTicks = boot;
    if((St.chartKeys && St.chartKeys.length) || boot > 80){
      if(!(St.chartKeys && St.chartKeys.length)) R.err = '研报没从云端加载出来（chartKeys=0）';
      R.bootSrc = (St.src || '');
      for(var i = 0; i < steps.length; i++){
        var st = steps[i];
        R.lastStep = st.n;
        try{ st.f(); }
        catch(e){
          R.errs = R.errs || [];
          R.errs.push(st.n + ' -> ' + String((e && e.message) || e));
        }
        out();
      }
      R.stage = 'done'; out();
      return;
    }
    setTimeout(waitBoot, 100);
  })();
})();
</script>
'''
js = PROBE

s = open(SRC, encoding='utf-8').read()
# ⚠️⚠️ 两个坑（上一轮实踩过，这里原样保留）：
#  ① ECharts 源码里含 `'</body></html>'` 这种字符串字面量 → 必须从**最后一个** </body> 注入。
#  ② 研报页自己在 <head> 里装了 window.onerror（写 __RPT_ERR），会覆盖我们的钩子
#     → 用 addEventListener('error') 另挂一份，并直接读 __RPT_ERR。
onerr = ('<script>window.__R={err:[],stage:"boot"};'
         'window.addEventListener("error",function(e){'
         'window.__R.err.push("err:"+String(e.message||e)+" @"+(e.lineno||0));});'
         'window.addEventListener("unhandledrejection",function(e){'
         'window.__R.err.push("rej:"+String((e.reason&&e.reason.message)||e.reason));});'
         '</script>')
assert '<head>' in s
s = s.replace('<head>', '<head>\n' + onerr, 1)
assert '</body>' in s
_i = s.rfind('</body>')
s = s[:_i] + js + '\n' + s[_i:]
open(OUT, 'w', encoding='utf-8').write(s)
print('[1] 探针页已生成：%s（%d 字节）' % (OUT, os.path.getsize(OUT)))

NODE = r'C:\Users\50522\.workbuddy\binaries\node\versions\22.22.2-3\node.exe'
_core = js.split('<script>')[1].split('</script>')[0]
open(os.path.join(BASE, 'build', '_tmp_tablerows.js'), 'w', encoding='utf-8').write(_core)
_c = subprocess.run([NODE, '--check', os.path.join(BASE, 'build', '_tmp_tablerows.js')],
                    capture_output=True, text=True)
if _c.returncode != 0:
    print('[1b] 注入脚本语法错误：\n' + (_c.stderr or '')[-1500:])
    raise SystemExit(1)
print('[1b] 注入脚本 node --check 通过')


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


os.chdir(os.path.join(BASE, 'build'))
socketserver.TCPServer.allow_reuse_address = True
httpd = socketserver.TCPServer(('127.0.0.1', PORT), Quiet)
threading.Thread(target=httpd.serve_forever, daemon=True).start()
print('[2] 本地 http：http://127.0.0.1:%d/' % PORT)

edge = None
for c in [r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
          r'C:\Program Files\Microsoft\Edge\Application\msedge.exe']:
    if os.path.exists(c):
        edge = c
        break
assert edge, '找不到 msedge.exe'
print('[3] Edge：%s' % edge)

prof = os.path.join(BASE, 'build', '_probe_profile_tablerows')
os.makedirs(prof, exist_ok=True)          # 固定 profile，不删目录（safe-delete 守卫）
url = 'http://127.0.0.1:%d/_probe_tablerows.html?code=%s' % (PORT, CODE)
print('[4] 启动 headless Edge（真取云端研报）…')
r = subprocess.run([edge, '--headless=new', '--disable-gpu', '--no-sandbox', '--hide-scrollbars',
                    '--user-data-dir=' + prof, '--virtual-time-budget=90000', '--dump-dom', url],
                   capture_output=True, timeout=420)
dom = r.stdout.decode('utf-8', 'ignore')
print('    DOM 长度 %d' % len(dom))

m = re.search(r'PROBE_JSON:(\{.*?\})</div>', dom, re.S) or re.search(r'PROBE_JSON:(\{.*\})', dom, re.S)
ok = fail = 0


def chk(name, cond, extra=''):
    global ok, fail
    if cond:
        ok += 1
        print('  [OK]   ' + name)
    else:
        fail += 1
        print('  [FAIL] ' + name + ('   → ' + str(extra) if extra != '' else ''))


print('\n' + '=' * 78)
print('表格「增加行 / 删除行」端到端验收')
print('=' * 78)

if not m:
    open(os.path.join(BASE, 'build', '_probe_tablerows_dom.txt'), 'w', encoding='utf-8').write(dom)
    print('[FAIL] 探针没有回传结果，DOM 已存 build/_probe_tablerows_dom.txt')
    print('\n结果：0 通过 / 1 失败')
    raise SystemExit(1)

d = json.loads(html.unescape(m.group(1)))     # ⚠️ --dump-dom 会把 < > & 变实体，先还原
print('阶段：%s   最后一步：%s' % (d.get('stage'), d.get('lastStep')))
print('图表数：%s   当前键：%s   饼图键：%s' % (d.get('chartKeys'), d.get('selKey'), d.get('pieKey')))
print('表格模块：%s（%s）' % (d.get('modNo'), d.get('tableSrc')))
print()

chk('JS 零未捕获错误', not d.get('err'), d.get('err'))
chk('每一步都没抛异常（抛了会逐条列在这）', not (d.get('errs') or []), d.get('errs'))
chk('页面自己的错误钩子为空（含 ECharts）', not (d.get('pageErrs') or []), d.get('pageErrs'))
chk('ECharts 没被打断（echarts 在 + 有 canvas）',
    d.get('echartsUp') is True and (d.get('chartsRendered') or 0) > 0,
    '%s / %s' % (d.get('echartsUp'), d.get('chartsRendered')))
chk('阶段跑完', d.get('stage') == 'done', d.get('stage'))
chk('真云端研报已加载', (d.get('chartKeys') or 0) > 0, d.get('chartKeys'))
chk('哨兵 RPASS_OK 可达', d.get('passOk') is True)

# ---------------- A. 图表数据表 ----------------
g = d.get('gateGrid') or {}
chk('A1 工具条里「＋ 增加行」「－ 删除行」各 1 个', d.get('btnAdd') == 1 and d.get('btnDel') == 1,
    '%s / %s' % (d.get('btnAdd'), d.get('btnDel')))
chk('A1 每行行号列都有 ✕ 按钮', (d.get('gx0') or 0) == (d.get('n0') or -1) and (d.get('gx0') or 0) > 0,
    '%s 个 ✕ vs %s 行' % (d.get('gx0'), d.get('n0')))
chk('A1 删行挂门禁（act=删除）+ 插行/工具栏按钮不进 RGATE（避免二次弹框）',
    g.get('gated') is True and g.get('act') == '删除' and g.get('danger') is False
    and g.get('addGated') is False and g.get('focusGated') is False, g)

chk('A2 不带哨兵删行 → 弹出密码框', d.get('gateModal') is True, d.get('gateModal'))
chk('A2 弹框期间行数一行没少（证明门禁真拦得住，不是装饰）', d.get('gateHeld') is True,
    '%s 行 → %s 行' % (d.get('nGateBefore'), d.get('n0')))
chk('A2 取消后遮罩关闭', d.get('gateModalClosed') is True)

n0 = d.get('n0') or 0
chk('A3 增加行：行数 +1', d.get('n1') == n0 + 1, '%s → %s' % (n0, d.get('n1')))
chk('A3 末行是空行', (d.get('last1') or ['x']) == [''] * len(d.get('head1') or []), d.get('last1'))
chk('A3 计数文案 = N 行 × M 个系列',
    (d.get('info1') or '').startswith('%d 行 ×' % (n0 + 1)), d.get('info1'))
chk('A3 行号列重排成 1..N',
    d.get('ix1') == [str(i + 1) for i in range(n0 + 1)], d.get('ix1'))
chk('A3 ✕ 数量跟着行数走', d.get('gx1') == n0 + 1, d.get('gx1'))
chk('A3 表头（系列名）不变', d.get('head1') == d.get('head0'), d.get('head1'))

chk('A4 手改的值 999.5 在加行后仍在（重画没冲掉手改）', d.get('keptVal') == '999.5', d.get('keptVal'))
chk('A4 加行后行数 = 原 +2', d.get('n2') == n0 + 2, d.get('n2'))

chk('A5 删行：行数 -1', d.get('n3') == n0 + 1, '%s → %s' % (d.get('n2'), d.get('n3')))
chk('A5 删的正是第 2 行（原第 3 行顶上来了）', d.get('shiftOk') is True, d.get('shiftOk'))
chk('A5 第 1 行（含手改的 999.5）没被误删',
    (d.get('kept0') or ['', ''])[1] == '999.5', d.get('kept0'))
chk('A5 序号重排', d.get('ix3') == [str(i + 1) for i in range(n0 + 1)], d.get('ix3'))

chk('A6 保存干跑：series.data 长度 = 表格行数',
    d.get('dataAfter') == d.get('jsonRows'), '%s vs %s' % (d.get('dataAfter'), d.get('jsonRows')))
chk('A6 保存干跑：xAxis 类别数 = 表格行数',
    d.get('catsAfter') == d.get('jsonRows'), '%s vs %s' % (d.get('catsAfter'), d.get('jsonRows')))
chk('A6 末行数据落位正确（空行 → 空值）', d.get('lastDataVal') in (None, '', 0), d.get('lastDataVal'))
chk('A6 整个过程表头没变过', d.get('headUnchanged') is True)

chk('A7 没点进格子 → 删的是最后一行（删掉的下标 = 删后行数）',
    d.get('focusIdxNoCell') == d.get('n4') and d.get('lastGone') is True,
    'idx=%s n4=%s lastGone=%s' % (d.get('focusIdxNoCell'), d.get('n4'), d.get('lastGone')))
chk('A8 真 focus 落在第 1 行（activeElement.data-r=0）', d.get('realActiveR') == '0', d.get('realActiveR'))
chk('A8 点进第 1 行后删的确实是第 0 行', d.get('focusIdxCell') == 0, d.get('focusIdxCell'))
chk('A8 原第 1 行没了、原第 2 行顶上来',
    d.get('firstNow') == d.get('firstWant') and d.get('firstVanish') is True,
    '%s vs %s' % (d.get('firstNow'), d.get('firstWant')))
chk('A9 遮蔽 activeElement 后取到 data-r=1 → 删下标 1', d.get('shadowIdx') == 1 and
    d.get('shadowRemoved') is True, 'idx=%s removed=%s' % (d.get('shadowIdx'), d.get('shadowRemoved')))
chk('A10 删到只剩 1 行', d.get('oneRow') == 1, d.get('oneRow'))
chk('A10 只剩 1 行时拒绝删（表没被删空）', d.get('refuseHeld') is True and
    '至少' in (d.get('refuseToast') or ''), d.get('refuseToast'))
if d.get('pieSkipped'):
    chk('A11 无饼图，跳过', True)
else:
    chk('A11 饼图加行：行数 +1 且末行两格为空',
        d.get('pieN1') == (d.get('pieN0') or 0) + 1 and d.get('pieLastEmpty') is True,
        '%s → %s / %s' % (d.get('pieN0'), d.get('pieN1'), d.get('pieLastEmpty')))
    chk('A11 空行不会变成 0 号扇区（保存干跑后扇区数不变）',
        d.get('pieSaved') == d.get('pieN0'), '%s vs %s' % (d.get('pieSaved'), d.get('pieN0')))

# ---------------- B. 模块正文表格 ----------------
gr = d.get('gateRte') or {}
chk('B1 正文富文本工具条出现「＋ 行」「－ 行」',
    d.get('rteAddBtn') == 1 and d.get('rteDelBtn') == 1,
    '%s / %s' % (d.get('rteAddBtn'), d.get('rteDelBtn')))
chk('B1 两个按钮都带 onmousedown=return false（否则选区会被抢走）',
    d.get('rteNoBlur') == [1, 1], d.get('rteNoBlur'))
chk('B1 模块表格已渲染（模块 %s，来源 %s，有表头 %s）',
    d.get('rteHasTable') is True and (d.get('trs0') or 0) >= 3 and d.get('usedThead') is True,
    '%s / %s 行 / thead=%s' % (d.get('rteHasTable'), d.get('trs0'), d.get('usedThead')))
chk('B1 删行挂门禁（act=删除，但插行不进）',
    gr.get('gated') is True and gr.get('act') == '删除' and gr.get('danger') is False, gr)

chk('B2 光标能被识别为「在表格某一行里」', d.get('caretFound') is True, d.get('caretFound'))
chk('B2 插行后行数 +1', d.get('trAfter') == (d.get('trs0') or 0) + 1,
    '%s → %s' % (d.get('trs0'), d.get('trAfter')))
chk('B2 新行列数 = 目标行列数（%s）' % d.get('ncell'),
    d.get('newCells') == d.get('ncell'), '%s vs %s' % (d.get('newCells'), d.get('ncell')))
chk('B2 新行是 <td>（不会变成第二个表头）', d.get('newIsTd') is True)
chk('B2 新行样式照抄同列单元格', d.get('styleCopied') is True)
chk('B2 新行是空的', d.get('newEmpty') is True)
chk('B2 ★ UI.rteDirty 被置位（否则保存时会被静默丢掉）', d.get('dirty1') == 1, d.get('dirty1'))
chk('B2 ★ rteRead 读回的内容里行数也 +1（真的会存下去）',
    d.get('readBackTrs') == (d.get('readBackTrs0') or -99) + 1,
    '读回 %s ← %s（+1 才对）' % (d.get('readBackTrs'), d.get('readBackTrs0')))
chk('B2 光标落进新行（能接着打字）', d.get('caretInNew') is True)

if d.get('theadSkipped'):
    chk('B3 该表没有 thead，跳过（已由 B1 的补表分支兜住）', False, '未被覆盖')
else:
    chk('B3 光标在表头 → thead 行数不变（没多出第二个表头）',
        d.get('theadRows1') == d.get('theadRows0') == 1, '%s → %s' % (d.get('theadRows0'), d.get('theadRows1')))
    chk('B3 新行落在 tbody 第一行', d.get('tbodyRows1') == (d.get('tbodyRows0') or 0) + 1,
        '%s → %s' % (d.get('tbodyRows0'), d.get('tbodyRows1')))
    chk('B3 新行是 <td>，样式抄的是正文行（表头红底没被带下来）',
        d.get('headNewIsTd') is True and d.get('headNewStyle') == d.get('bodyStyle0')
        and d.get('headNewStyle') != d.get('thStyle'),
        'new=%r 正文行=%r 表头=%r' % (d.get('headNewStyle'), d.get('bodyStyle0'), d.get('thStyle')))

if d.get('theadSkippedB4'):
    chk('B4 该表没有 thead，跳过', False, '未被覆盖')
else:
    chk('B4 表头行删不掉（行数不变 + 提示）',
        d.get('headRefuse') is True and '表头' in (d.get('headRefuseToast') or ''),
        d.get('headRefuseToast'))
chk('B5 删正文行：tbody 行数 -1', d.get('bodyAfter') == d.get('bodyWant'),
    '%s vs %s' % (d.get('bodyAfter'), d.get('bodyWant')))
chk('B5 被删的那一行在 DOM 里真的没了', d.get('victimGone') is True)
chk('B5 删完仍然置位 dirty + 读回行数也 -1（删得掉、存得下）',
    d.get('dirty2') == 1 and d.get('readBackTrs2') == (d.get('readBackTrs2a') or 99) - 1,
    'dirty=%s 读回 %s ← %s' % (d.get('dirty2'), d.get('readBackTrs2'), d.get('readBackTrs2a')))

chk('B6 删到只剩 1 行', d.get('oneBodyRow') == 1, d.get('oneBodyRow'))
chk('B6 只剩 1 行时拒绝删（表没被删空）', d.get('lastRefuse') is True and
    '至少' in (d.get('lastRefuseToast') or ''), d.get('lastRefuseToast'))
chk('B7 光标不在表格里 → 明确拒绝且 DOM 不变',
    d.get('outOfTable') is True and d.get('outHeld') is True and
    '光标' in (d.get('outToast') or ''), d.get('outToast'))

chk('B8 不带哨兵删正文行 → 弹密码框', d.get('rteModal') is True, d.get('rteModal'))
chk('B8 弹框期间行数不变', d.get('rteHeld') is True)
chk('B8 插行不弹框（when 分支直通）且真的插上了',
    d.get('rteNoModalForAdd') is True and d.get('rteAddedNoTick') is True,
    '%s / %s' % (d.get('rteNoModalForAdd'), d.get('rteAddedNoTick')))

print()
print('图表数据表最后状态（切到「模块」页前）：%s 行 · 计数「%s」· 表头 %s'
      % (d.get('gridLastRows'), d.get('gridLastInfo'), d.get('head0')))
print('正文表格（模块 %s，来源 %s）：%s 行 × %s 列'
      % (d.get('modNo'), d.get('tableSrc'), d.get('finalRteTrs'), d.get('finalRteCells')))
print('\n' + '=' * 78)
print('结果：%d 通过 / %d 失败' % (ok, fail))
print('=' * 78)
raise SystemExit(0 if fail == 0 else 1)
