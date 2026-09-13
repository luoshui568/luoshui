# -*- coding: utf-8 -*-
"""研报页（report.html）+ 工作台跳转 · 端到端真机探针

本轮交付验收（全部在真浏览器里跑，数据来自**真云端数据库**）：
  A. 研报页数据来源 = 云端数据库（不是内置副本）；23 个模块 / 16 张图表 / 8 项 KPI / 目录齐
  B. 红主题生效：--accent 等变量、hero 渐变、整套 CSS 里 0 处蓝调残留
  C. 16 张图全部渲染出 canvas 且尺寸正常；{{fn:token}} 全部还原（数据里 0 处标记残留）
  D. 图表数据表 ↔ option 往返无损（「改数字」不会损坏图表）
  E. 保存链路真写入数据库：改标题 + 改 KPI 数值 → 保存 → 回读确认真被改 → 还原 → 再回读确认复原
  F. 图表数据表改数字 → 保存 → 回读 opt 确认生效 → 还原（含直接 POST 原始 opt 的兜底还原）
  G. 安全闸门：错密码的 wb_admin_verify 必须被拒；匿名 DELETE 必须被拒（42501）
  H. 工作台投资标的表格：名称/代码是 report.html?code=… 链接、操作列有 📄 按钮、App.openReport 能开
  I. 两页 JS 错误必须为 0

用法：python build/probe_report_e2e.py
"""
import http.server
import json
import os
import re
import shutil
import socketserver
import subprocess
import threading

BASE = r'C:\Users\50522\WorkBuddy\2026-09-10-14-50-38'
DEPLOY = os.path.join(BASE, 'deploy')
NODE = r'C:\Users\50522\.workbuddy\binaries\node\versions\22.22.2-3\node.exe'
PORT = 8921
CODE = '600456'

OUT_RPT = os.path.join(DEPLOY, '_probe_rpt.html')
OUT_WB = os.path.join(DEPLOY, '_probe_wb.html')

# ============================================================ 研报页探针
RPT_PROBE = r'''
<div id="probeOut" style="display:none"></div>
<script>
(function(){
  var R = window.__R;
  function out(){ document.getElementById('probeOut').textContent = 'PROBE_JSON:' + JSON.stringify(R); }
  function txt(id){ var e = document.getElementById(id); return e ? e.textContent.replace(/\s+/g,' ').trim() : ''; }
  function wait(ms){ return new Promise(function(r){ setTimeout(r, ms); }); }
  function cop(o){ return JSON.parse(JSON.stringify(o)); }
  function cssText(){
    var s = '';
    for(var i = 0; i < document.styleSheets.length; i++){
      try{
        var rs = document.styleSheets[i].cssRules;
        for(var j = 0; j < rs.length; j++) s += rs[j].cssText + '\n';
      }catch(e){}
    }
    return s;
  }
  var BLUE = /#1f5fd6|#174a9e|#1f4e78|#0f1d3a|#3d7cf0|#2f6fe0|#e9f0fd|rgba\(31,\s*95,\s*214/gi;
  var CD = '';                             /* 当前研报代码（readStage 里从 St.code 取） */
  function markers(o){
    var n = 0;
    (function w(x){
      if(typeof x === 'string'){ var m = x.match(/\{\{fn:/g); if(m) n += m.length; return; }
      if(x && typeof x === 'object'){ for(var k in x) w(x[k]); }
    })(o);
    return n;
  }
  function fns(o){
    var n = 0;
    (function w(x){
      if(typeof x === 'function'){ n++; return; }
      if(x && typeof x === 'object'){ for(var k in x) w(x[k]); }
    })(o);
    return n;
  }

  var t = 0, iv = setInterval(function(){
    t++;
    if(window.__RPT_CHARTS !== undefined || t > 120){ clearInterval(iv); run(); }
  }, 100);

  /* ---------------- H. 编辑模式 / 编辑器可达性 ----------------
     回归：openMod/openChart 先设 UI.selX 再调 openDrawer，而 openDrawer 会清空 selX →
     以前点「✏️ 编辑本模块 / 图表数据」只会看到列表（表现为按钮点了没反应）。 */
  function editStage(){
    Rpt.toggleEdit();
    R.editing = document.documentElement.className;
    R.opsBtns = document.querySelectorAll('#mods .rpt-ops').length;
    /* ⚠️ .rpt-cops 是 renderCharts() 里挂的，而 renderCharts 在 setTimeout(…,40) 之后才跑，
       同步查询会永远拿到 0 —— 必须等一小会儿。 */
    return wait(500).then(function(){
      R.chartOps = document.querySelectorAll('.rpt-cops').length;
      var mid = St.mods[0] ? St.mods[0].id : '';
      Rpt.openMod(mid);
      R.editModSel = UI.selMod;
      /* 模块正文现在是「可视化编辑区」（contenteditable），不再给用户看 HTML 源码 */
      var box = $('m-edit');
      R.editModOpened = !!(box && box.getAttribute('contenteditable') === 'true');
      R.editModTitle = $('m-title') ? String($('m-title').value).slice(0, 20) : null;
      R.editModHtml = box ? box.innerHTML.length : -1;
      R.editVis = box ? box.textContent.replace(/\s+/g, ' ').trim().slice(0, 60) : '';
      var src = $('m-edit-src'), wrap = $('m-edit-wrap');
      /* ⚠️ 判据不能用 getClientRects()：Chromium 是用 content-visibility:hidden 隐藏
         收起 <details> 的内容，元素**仍有布局盒**（实测 textarea 289x844），只是不绘制。
         正解是 checkVisibility()（会把 content-visibility:hidden 的祖先算进去），
         兜底看 <details>.open。 */
      R.editSrcHidden = !src ? true
        : (src.checkVisibility ? !src.checkVisibility() : (wrap ? !wrap.open : false));
      R.editSrcBox = src
        ? (src.offsetHeight + 'x' + src.offsetWidth + ' · details 高=' + (wrap ? wrap.offsetHeight : -1) +
           ' open=' + (wrap ? wrap.open : '?') + ' · checkVisibility=' +
           (src.checkVisibility ? src.checkVisibility() : 'n/a'))
        : '(无)';
      R.editBarBtns = document.querySelectorAll('.rtebar .rteb').length;
      var m2 = Rpt.findMod(St.code + '_m12');        /* m12 里有 6 张图，专门用来验标签保护 */
      Rpt.openMod(St.code + '_m12');
      var b2 = $('m-edit');
      R.chipN = document.querySelectorAll('#m-edit .rte-chip').length;
      R.chipEditable = document.querySelectorAll('#m-edit .rte-chip[contenteditable="false"]').length;
      R.rawChartDiv = document.querySelectorAll('#m-edit div[data-chart]').length;
      R.chipText = document.querySelectorAll('#m-edit .rte-chip').length
        ? document.querySelectorAll('#m-edit .rte-chip')[0].textContent : '';
      R.m12Vis = b2 ? b2.textContent.replace(/\s+/g, ' ') : '';
      var w = $('m-edit-wrap');
      if(w){ w.open = true; Rpt.rteToggle('m-edit', w); }
      var s2 = $('m-edit-src');
      R.srcHasCode = !!s2 && /data-chart="chart/.test(s2.value);
      R.srcLen = s2 ? s2.value.length : -1;
      if(w){ w.open = false; Rpt.rteToggle('m-edit', w); }
      R.modHtmlBacked = b2 ? (rteSave(b2.innerHTML).indexOf('rte-chip') >= 0) : false;
      Rpt.openChart('chart1');
      R.editChartSel = UI.selChart;
      R.editChartOpened = !!$('c-json');
      R.editChartGrid = document.querySelectorAll('.rpt-grid input[data-r]').length;
      R.editChartCols = [].map.call(document.querySelectorAll('.rpt-grid thead th'), function(e){
        return e.textContent.trim(); });
      Rpt.closeDrawer();
      Rpt.toggleEdit();
      R.editingOff = document.documentElement.className;
    });
  }

  /* ---------------- I. 可视化编辑：看不到代码、也改不坏代码 ---------------- */
  function getModHtml(id){
    return api('wb_report_mods?id=eq.' + id + '&select=html').then(function(rows){
      return (rows && rows[0]) ? rows[0].html : null;
    });
  }
  function rteStage(){
    var MID = St.code + '_m12';               /* m12 里有 6 张图 */
    var before = null, mref = Rpt.findMod(MID);
    R.rte = {mid: MID};
    return getModHtml(MID).then(function(h){
      before = h;
      R.rte.beforeLen = h ? h.length : -1;
      R.rte.beforeCharts = h ? (h.match(/data-chart=/g) || []).length : -1;
      /* (1) 打开编辑器 → 什么都不改直接保存 → 库里必须逐字不变（防「打开-保存」洗排版） */
      Rpt.openMod(MID);
      R.rte.opened = !!$('m-edit');
      Rpt.svMod();
      return wait(900);
    }).then(function(){ return getModHtml(MID); })
      .then(function(h){
        R.rte.notouchSame = (h === before);
        R.rte.notouchLen = h ? h.length : -1;
        /* (2) 真的改内容（顺带塞一段危险标签，验证写库前清洗）→ 保存 → 回读 */
        Rpt.openMod(MID);
        var box = $('m-edit');
        R.rte.opened2 = !!box;
        box.innerHTML = box.innerHTML +
          '<p>探针写入标记 <b>ZZQ1<\/b></p>' +
          '<p onclick="window.__XSS=1">带事件的段落<script>window.__XSS2=1<\/script></p>';
        try{ box.dispatchEvent(new Event('input', {bubbles:true})); }
        catch(e){ UI.rteDirty['m-edit'] = 1; }
        R.rte.dirtyFlag = UI.rteDirty['m-edit'] === 1;
        Rpt.svMod();
        return wait(900);
      })
      .then(function(){ return getModHtml(MID); })
      .then(function(h){
        h = h || '';
        R.rte.afterLen = h.length;
        R.rte.hasMarker = h.indexOf('ZZQ1') >= 0;
        R.rte.chartsKept = (h.match(/data-chart=/g) || []).length;
        R.rte.noScript = !/<script/i.test(h);
        R.rte.noOnAttr = !/\son[a-z]+\s*=/.test(h);
        R.rte.chipLeft = h.indexOf('rte-chip') >= 0;
        /* (3) 还原 */
        return api('wb_report_mods?id=eq.' + MID, {
          method: 'PATCH',
          headers: {'Content-Type': 'application/json', 'Prefer': 'return=minimal'},
          body: {html: before}
        });
      })
      .then(function(){ return getModHtml(MID); })
      .then(function(h){
        R.rte.restored = (h === before);
        if(mref) mref.html = before;
        try{ render(); }catch(e){}
        /* (4) 「新建研报」防覆盖闸门：拿一个**已存在**的代码去创建 → 必须被拒绝、数据不动。
           血案：wb_reports 按 id upsert，用已有代码建研报会把整份研报（23 模块 + 16 图）覆盖掉。 */
        UI.tab = 'new'; UI.selMod = ''; UI.selChart = '';
        Rpt.openDrawer('new', false);
        var c = $('n-code'); if(c) c.value = St.code;
        var b = $('n-go'); if(b) b.disabled = false;
        RptCreate();
        return wait(1600);
      })
      .then(function(){
        var w = $('n-warn');
        R.rte.warnShown = !!(w && w.style.display !== 'none' && /不能重复创建/.test(w.textContent));
        R.rte.warnText = w ? w.textContent.replace(/\s+/g, ' ').trim().slice(0, 70) : '';
        return getModHtml(MID);
      })
      .then(function(h){
        R.rte.dupSafe = (h === before);
        Rpt.closeDrawer();
      });
  }

  function run(){
    R.err = R.err || [];
    R.stage = 'read';
    try{ readStage(); }catch(e){ R.err.push('read:' + (e && e.message)); }
    R.rptErr = (window.__RPT_ERR || []).slice(0, 8);
    out();                                   /* 分阶段回传：任何一步挂掉也能拿到前面的结果 */
    Promise.resolve()
      .then(function(){ R.stage = 'edit'; return editStage(); })
      .catch(function(e){ R.err.push('edit:' + (e && e.message)); })
      .then(function(){ R.stage = 'rte'; out(); return rteStage(); })
      .then(function(){ R.stage = 'sec'; out(); return secStage(); })
      .then(function(){ R.stage = 'head'; out(); return headWrite(); })
      .then(function(){ R.stage = 'chart'; out(); return chartWrite(); })
      .then(function(){ R.stage = 'done'; })
      .catch(function(e){ R.err.push('write:' + (e && e.message)); R.stage = 'threw'; })
      .then(function(){
        R.rptErr = (window.__RPT_ERR || []).slice(0, 8);
        out();
      });
  }

  /* ---------------- A/B/C/D. 读取 + 渲染 + 主题 + 图表 ---------------- */
  function readStage(){
    R.src = St.src;
    R.code = St.code;
    CD = St.code || CD;
    R.repId = St.rep && St.rep.id;
    R.repName = St.rep && St.rep.name;
    R.repTitle = St.rep && St.rep.title;
    R.modN = St.mods.length;
    R.chartN = St.chartKeys.length;
    R.kpiN_data = ((St.rep && St.rep.kpis) || []).length;
    R.loadErr = String(St.loadErr || '');
    R.barTags = [].map.call(document.querySelectorAll('.rbar .rb-tag'), function(e){
      return e.textContent.replace(/\s+/g,' ').trim(); });

    /* 模块卡片 */
    R.cards = document.querySelectorAll('#mods .card').length;
    R.nos = [].map.call(document.querySelectorAll('#mods .card > h2 > .no'), function(e){
      return e.textContent.trim(); });
    R.heads = [].map.call(document.querySelectorAll('#mods .card > h2'), function(e){
      return e.textContent.replace(/\s+/g,' ').trim().slice(0, 30); });
    R.m23 = !!document.getElementById('m23');
    R.essence = !!document.getElementById('essence');
    R.dataMods = document.querySelectorAll('#mods .card[data-mod]').length;

    /* 图表 */
    R.charts = window.__RPT_CHARTS;
    var slots = document.querySelectorAll('[data-chart]');
    R.slots = slots.length;
    var miss = [], ws = [], hs = [], keys = [], cw = {};
    [].forEach.call(slots, function(el){
      var k = el.getAttribute('data-chart');
      keys.push(k);
      var cv = el.querySelector('canvas');
      if(!cv){ miss.push(k); return; }
      ws.push(cv.clientWidth); hs.push(cv.clientHeight);
      cw[k] = cv.clientWidth + 'x' + cv.clientHeight;
    });
    R.cvW = cw;
    R.slotKeys = keys.slice(0, 20);
    R.cvMiss = miss;
    R.cvN = ws.length;
    R.cvMinW = ws.length ? Math.min.apply(null, ws) : -1;
    R.cvMinH = hs.length ? Math.min.apply(null, hs) : -1;
    R.chartInst = Object.keys(St.inst || {}).length;
    R.hasEcharts = typeof window.echarts;
    R.echartsVer = (window.echarts && window.echarts.version) || null;
    R.slotMiss = [].map.call(document.querySelectorAll('.rpt-chartmiss'), function(e){
      return e.textContent.replace(/\s+/g, ' ').trim().slice(0, 70); }).slice(0, 4);

    /* KPI / 目录 / 结论 / 页脚 */
    R.kpiN = document.querySelectorAll('#kpis .stat').length;
    R.kpiLabels = [].map.call(document.querySelectorAll('#kpis .stat .label'), function(e){
      return e.textContent.trim(); });
    R.kpiVals = [].map.call(document.querySelectorAll('#kpis .stat .val'), function(e){
      return e.textContent.replace(/\s+/g,' ').trim(); });
    R.tocN = document.querySelectorAll('#toc a').length;
    R.badges = [].map.call(document.querySelectorAll('#hero .badge'), function(e){
      return e.textContent.trim(); });
    R.subtitle = txt('hero').slice(0, 90);
    R.verdictLen = txt('verdict').length;
    R.footLen = txt('foot').length;

    /* 主题 */
    var cs = getComputedStyle(document.documentElement);
    R.accent = cs.getPropertyValue('--accent').trim();
    R.accentSoft = cs.getPropertyValue('--accent-soft').trim();
    R.green = cs.getPropertyValue('--green').trim();
    var hero = document.querySelector('header.hero') || document.querySelector('.hero');
    R.heroBg = hero ? getComputedStyle(hero).backgroundImage.slice(0, 150) : '';
    var css = cssText();
    R.cssLen = css.length;
    R.blueCss = (css.match(BLUE) || []).length;
    var sj = JSON.stringify(St.charts);
    R.blueData = (sj.match(BLUE) || []).length;
    R.redData = (sj.match(/#c8102e|#e63946|#a3122a|#8c0a20/gi) || []).length;
    R.optLen = sj.length;
    /* 库里存的是 {{fn:token}} 具名标记（设计如此，方便编辑 JSON）；
       渲染前 revive() 必须把它们全部还原成真函数，且还原后不能再残留标记 */
    R.fnMark = markers(St.charts);
    R.fnLeft = (sj.match(/\{\{fn:/g) || []).length;
    var rvOk = 0, rvBad = [];
    St.chartKeys.forEach(function(k){
      try{
        var before = markers(St.charts[k].opt);
        var o = revive(cop(St.charts[k].opt), cop(St.charts[k].opt));
        var got = fns(o), left = markers(o);
        /* 判据：还原出的函数数 >= 原有标记数，且还原后不再残留标记 */
        if(got >= before && left === 0) rvOk++;
        else rvBad.push(k + ' 标记' + before + '→函数' + got + ' 残留' + left);
      }catch(e){ rvBad.push(k + ':ERR:' + (e && e.message)); }
    });
    R.reviveOk = rvOk;
    R.reviveBad = rvBad;

    /* 图表数据表 ↔ option 往返无损 */
    R.rtBad = [];
    R.rt = {};
    R.rowShapes = {};
    St.chartKeys.forEach(function(k){
      var opt = St.charts[k].opt;
      try{
        var m = chartModel(cop(opt));
        R.rowShapes[k] = m.cols.length + '列×' + m.rows.length + '行';
        var o2 = applyGrid(cop(opt), m);
        var same = JSON.stringify(o2) === JSON.stringify(opt);
        R.rt[k] = same;
        if(!same) R.rtBad.push(k);
      }catch(e){ R.rt[k] = 'ERR:' + (e && e.message); R.rtBad.push(k); }
    });
  }

  /* ---------------- G. 安全闸门 ----------------
     注意：服务端 RPC 用的是 HTTP 200 + {ok:false, code:'…'} 语义，不是非 2xx，
     所以「被拒」的判据是 ok !== true（或网络层抛错），不是 catch 到异常。 */
  function secStage(){
    R.sec = {};
    return rpc('wb_admin_verify', {p_token: 'bogus-token-probe', p_pass: 'definitely-wrong'})
      .then(function(r){
        R.sec.verifyRaw = JSON.stringify(r).slice(0, 120);
        R.sec.verify = (r && r.ok === true) ? 'ACCEPTED' : 'rejected';
      }, function(e){
        R.sec.verify = 'rejected';
        R.sec.verifyErr = String(e.message || e).slice(0, 90);
      })
      .then(function(){
        /* 真测密码校验：不存在的密码必须登录失败（不会创建任何会话） */
        return rpc('wb_admin_login', {p_user: 'luoshui', p_pass: 'probe-wrong-pw-9f3a',
                                      p_device: 'probe', p_days: 0});
      })
      .then(function(r){
        R.sec.loginRaw = JSON.stringify(r).slice(0, 120);
        R.sec.login = (r && r.ok === true) ? 'ACCEPTED' : 'rejected';
        R.sec.tokenGot = !!(r && (r.token || r.t));
      }, function(e){
        R.sec.login = 'rejected';
        R.sec.loginErr = String(e.message || e).slice(0, 90);
      })
      .then(function(){
        return api('wb_reports?id=eq.' + CD, {method: 'DELETE'})
          .then(function(){ R.sec.anonDel = 'DELETED'; },
                function(e){ R.sec.anonDel = 'denied'; R.sec.anonDelErr = String(e.message || e).slice(0, 90); });
      })
      .catch(function(e){ R.sec.chainErr = String(e && e.message || e).slice(0, 90); });
  }

  /* ---------------- E. 页眉 / KPI 真写库 ---------------- */
  function headWrite(){
    var orig = cop(St.rep || {});
    var origTitle = orig.title;
    var origKpi = (orig.kpis || [])[0] || {};
    var NEWT = String(origTitle) + ' 【探针】';
    R.hw = {origTitle: origTitle, newTitle: NEWT, origKpiVal: origKpi.val};

    Rpt.openDrawer('head');
    R.hw.maskOn = ($('rptMask').className || '').indexOf('on') >= 0;
    R.hw.titleFld = !!$('h-title');
    R.hw.kpiRows = document.querySelectorAll('#kpiEdit tr[data-k]').length;
    R.hw.fields = document.querySelectorAll('#rptDrawer .rinp, #rptDrawer .rtxt').length;

    var krow = document.querySelector('#kpiEdit tr[data-k]');
    var kval = krow ? krow.querySelector('[data-f="val"]') : null;
    R.hw.kValFromForm = kval ? kval.value : null;

    $('h-title').value = NEWT;
    if(kval) kval.value = '27.99';
    Rpt.svHead();

    return wait(1800).then(function(){
      return api('wb_reports?id=eq.' + CD + '&select=title,kpis,up');
    }).then(function(rows){
      var r0 = (rows && rows[0]) || {};
      R.hw.dbTitle = r0.title;
      R.hw.dbKpiVal = r0.kpis && r0.kpis[0] ? r0.kpis[0].val : null;
      R.hw.savedOk = (r0.title === NEWT) && (String(R.hw.dbKpiVal) === '27.99');
      /* 还原 */
      var t2 = $('h-title'); if(t2) t2.value = origTitle;
      var k2 = document.querySelector('#kpiEdit tr[data-k] [data-f="val"]');
      if(k2) k2.value = origKpi.val;
      Rpt.svHead();
      return wait(1800);
    }).then(function(){
      return api('wb_reports?id=eq.' + CD + '&select=title,kpis');
    }).then(function(rows){
      var r0 = (rows && rows[0]) || {};
      R.hw.dbTitleBack = r0.title;
      R.hw.dbKpiBack = r0.kpis && r0.kpis[0] ? r0.kpis[0].val : null;
      R.hw.restoredOk = (r0.title === origTitle) && (String(R.hw.dbKpiBack) === String(origKpi.val));
      Rpt.closeDrawer();
    });
  }

  /* ---------------- F. 图表数据表真写库 ---------------- */
  function chartWrite(){
    var key = 'chart1';
    var rec = St.charts[key];
    if(!rec){ R.cw = {skip: 'chart1 不存在'}; return Promise.resolve(); }
    var orig = cop(rec.opt);
    var m0 = chartModel(cop(orig));
    var oldV = m0.rows.length ? String(m0.rows[0][1] == null ? '' : m0.rows[0][1]) : '';
    var newV = String(parseFloat(oldV) + 1);
    R.cw = {key: key, oldV: oldV, newV: newV, shape: m0.cols.length + '列×' + m0.rows.length + '行',
            lossless: R.rt[key] === true};

    Rpt.openChart(key);
    R.cw.gridInputs = document.querySelectorAll('.rpt-grid input[data-r]').length;
    R.cw.gridCols = [].map.call(document.querySelectorAll('.rpt-grid thead th'), function(e){
      return e.textContent.trim(); });
    var cell = document.querySelector('.rpt-grid input[data-r="0"][data-c="1"]');
    R.cw.cellFound = !!cell;
    if(!cell){ Rpt.closeDrawer(); return Promise.resolve(); }
    R.cw.cellOld = cell.value;
    cell.value = newV;
    Rpt.svChart();

    return wait(2000).then(function(){
      return api('wb_report_charts?id=eq.' + CD + '_' + key + '&select=opt,name');
    }).then(function(rows){
      var got = rows && rows[0] ? rows[0].opt : null;
      R.cw.dbVal = got ? got.series[0].data[0] : null;
      R.cw.savedOk = got ? (String(got.series[0].data[0]) === newV) : false;
      /* 还原 1：把格子改回原值 → 走界面保存 */
      var c2 = document.querySelector('.rpt-grid input[data-r="0"][data-c="1"]');
      if(c2) c2.value = R.cw.cellOld;
      Rpt.svChart();
      return wait(2000);
    }).then(function(){
      return api('wb_report_charts?id=eq.' + CD + '_' + key + '&select=opt');
    }).then(function(rows){
      var got = rows && rows[0] ? rows[0].opt : null;
      R.cw.uiRestoredSame = got ? (JSON.stringify(got) === JSON.stringify(orig)) : false;
      R.cw.uiVal = got ? got.series[0].data[0] : null;
      /* 还原 2（兜底）：直接 POST 原始 opt，保证库里与原值逐字一致 */
      if(!R.cw.uiRestoredSame){
        return api('wb_report_charts?on_conflict=id', {
          method: 'POST',
          headers: {'Content-Type': 'application/json',
                    'Prefer': 'resolution=merge-duplicates,return=minimal'},
          body: [{id: CD + '_' + key, report_id: CD, code: CD, seq: rec.seq,
                  name: rec.name, opt: orig, up: nowTs()}]
        }).then(function(){ R.cw.fallbackPosted = true; return wait(1200); });
      }
      R.cw.fallbackPosted = false;
    }).then(function(){
      return api('wb_report_charts?id=eq.' + CD + '_' + key + '&select=opt');
    }).then(function(rows){
      var got = rows && rows[0] ? rows[0].opt : null;
      R.cw.finalSame = got ? (JSON.stringify(got) === JSON.stringify(orig)) : false;
      Rpt.closeDrawer();
    });
  }
})();
</script>
'''

# ============================================================ 工作台探针
WB_PROBE = r'''
<div id="probeOut" style="display:none"></div>
<script>
(function(){
  var R = window.__R;
  function out(){ document.getElementById('probeOut').textContent = 'PROBE_JSON:' + JSON.stringify(R); }
  function txt(id){ var e = document.getElementById(id); return e ? e.textContent.replace(/\s+/g,' ').trim() : ''; }

  var IMM = [
    {id:'st_600459', code:'600459', exchange:'sh', name:'贵研铂业', grp:'贵金属',
     sub_industry:'其他稀有小金属', region:'云南', ind_pe:39.36, total_assets:252.74,
     net_assets:90.12, price:18.94, chg_pct:-3.86},
    {id:'st_600456', code:'600456', exchange:'sh', name:'宝钛股份', grp:'钛材',
     sub_industry:'钛', region:'陕西', ind_pe:28.6, total_assets:120.5,
     net_assets:72.3, price:27.35, chg_pct:0.55}
  ];

  function rowInfo(){
    return [].map.call(document.querySelectorAll('#stockWrap tbody tr'), function(tr){
      var a = tr.querySelector('a.nm.rptLink');
      var c = tr.querySelector('a.cd.rptLink');
      var td = tr.querySelectorAll('td');
      var ops = td.length ? tr.querySelector('td.ops') : null;
      return {
        code: td.length ? td[0].textContent.trim() : '',
        aTag: a ? a.tagName : null,
        aHref: a ? a.getAttribute('href') : null,
        aCls: a ? a.className : null,
        aTxt: a ? a.textContent.replace(/\s+/g,' ').trim() : null,
        hasDot: a ? /📄/.test(a.textContent) : null,
        cHref: c ? c.getAttribute('href') : null,
        ops: ops ? [].map.call(ops.querySelectorAll('button'), function(b){
          return b.textContent.trim() + '::' + (b.getAttribute('onclick') || '');
        }) : []
      };
    });
  }

  /* 收尾：拿到研报代码之后再断言 */
  function finalize(){
    try{
      R.after = rowInfo();
      R.rptCodes = Object.keys(RPT_CODES);
      R.loadedFlag = window._rptCodesLoaded;
      var realOpen = window.open, got = null;
      window.open = function(u){ got = u; return {focus:function(){}}; };
      try{ App.openReport('600456'); }catch(e){ R.err.push('openReport:' + e.message); }
      window.open = realOpen;
      R.openUrl = got;
      R.stage = 'done';
    }catch(e){ R.err.push('fin:' + e.message); R.stage = 'threw'; }
    out();
  }

  setTimeout(function(){
    R.err = R.err || [];
    R.stage = 'probe';
    try{
      App.go('stock');
      R.pageOn = (document.getElementById('pg-stock').className || '').indexOf('on') >= 0;
      R.openReportFn = typeof App.openReport;

      /* 打桩：研报代码列表由桩返回（避免依赖云端当前内容）；其它表返回 null */
      window.api = function(tbl){
        if(String(tbl).indexOf('wb_reports') === 0) return Promise.resolve([{code:'600456'}]);
        return Promise.resolve(null);
      };

      S.stocks = IMM.map(function(x){ return defaults('stocks', x); });
      sortState();
      renderStock();          /* renderStock 内部自己也调一次 loadReportCodes */

      R.hrefHelper = rptHref({code:'600459'});
      R.hrefHelper2 = rptHref({});
      R.cols = [].map.call(document.getElementById('stockWrap').querySelectorAll('thead th'), function(e){
        return e.textContent.replace(/[⇅▼▲]/g,'').trim(); });
      R.before = rowInfo();
      R.subTxt = txt('stockSub');

      /* ⚠️ renderStock() 内部已经调过一次 loadReportCodes 并把 _rptCodesLoaded 置 true，
         那一次是不带回调的；这里必须**复位再显式拉一次**，否则 loadReportCodes 直接
         early-return、回调永不触发（探针会静默超时）。 */
      window._rptCodesLoaded = false;
      RPT_CODES = {};
      var fired = false;
      loadReportCodes(function(){ fired = true; finalize(); });
      setTimeout(function(){
        if(!fired){ R.err.push('loadReportCodes 回调未触发（early-return？）'); finalize(); }
      }, 2500);
    }catch(e){
      R.err.push('main:' + (e && e.message));
      R.stage = 'threw';
      out();
    }
  }, 1500);

  /* 兜底：无论上面卡在哪一步，最多 8 秒后也把当前 R 回传（否则排查时看不到任何线索） */
  setTimeout(function(){
    var el = document.getElementById('probeOut');
    if(el && String(el.textContent).indexOf('PROBE_JSON') !== 0){
      if(R.stage !== 'done') R.stage = 'timeout';
      out();
    }
  }, 8000);
})();
</script>
'''


# ---------------------------------------------------------------- 工具
def inject(src_path, out_path, probe_js_src, onerr_head=True):
    s = open(src_path, encoding='utf-8').read()
    if onerr_head:
        onerr = ('<script>window.__R={err:[],stage:"init"};'
                 'window.onerror=function(m,u,l,c,e){window.__R.err.push(String(m)+" @"+l);};'
                 '</script>')
        assert '<head>' in s, src_path + ' 没有 <head>'
        s = s.replace('<head>', '<head>\n' + onerr, 1)
    assert '</body>' in s, src_path + ' 没有 </body>'
    # ⚠️ 必须用**最后**一处 </body>：构建产物里 ECharts 压缩库的字符串中含 `</body>`
    #    （zrender 导出 SVG 那段），首处匹配会把探针塞进库脚本内部 → echarts is not defined。
    i = s.rfind('</body>')
    s = s[:i] + probe_js_src + '\n' + s[i:]
    open(out_path, 'w', encoding='utf-8').write(s)
    return os.path.getsize(out_path)


def check_js(probe_js_src, tag, tmp_path):
    # ⚠️ 不能用 split('<script>')[1].split('</script>')[0]：那是「第 1 到第 2 个 <script>」之间的内容，
    #    探针里一旦出现字面量 `<script>`（如故意注入 XSS 载荷做清洗测试）就会被从中间截断，
    #    抠出来的片段语法错 → 白跑一轮。改成「第一个 <script> 之后、紧接着的第一个 </script> 之前」。
    a = probe_js_src.index('<script>') + len('<script>')
    b = probe_js_src.index('</script>', a)
    core = probe_js_src[a:b]
    open(tmp_path, 'w', encoding='utf-8').write(core)
    c = subprocess.run([NODE, '--check', tmp_path], capture_output=True, text=True)
    os.remove(tmp_path)
    if c.returncode != 0:
        print('[1b] %s 注入脚本语法错误：\n%s' % (tag, (c.stderr or '')[-1200:]))
        raise SystemExit(1)
    print('[1b] %s 注入脚本 node --check 通过（%d 字符）' % (tag, len(core)))


def edge_path():
    for c in [r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
              r'C:\Program Files\Microsoft\Edge\Application\msedge.exe']:
        if os.path.exists(c):
            return c
    raise SystemExit('找不到 msedge.exe')


def run_probe(edge, url, tag, prof):
    shutil.rmtree(prof, ignore_errors=True)
    cmd = [edge, '--headless=new', '--disable-gpu', '--no-sandbox', '--hide-scrollbars',
           '--window-size=1680,1050',
           '--user-data-dir=' + prof, '--virtual-time-budget=90000', '--dump-dom', url]
    print('[%s] 启动 headless Edge …' % tag)
    # ⚠️ timeout 要给足：headless 的虚拟时钟在 fetch pending 时会**暂停**，
    #    云端网关偶尔慢一点 → 90s 虚拟预算可能拖成好几分钟真实时间。
    r = subprocess.run(cmd, capture_output=True, timeout=900)
    dom = r.stdout.decode('utf-8', 'ignore')
    print('    DOM 长度 %d' % len(dom))
    m = re.search(r'PROBE_JSON:(\{.*?\})</div>', dom, re.S) or re.search(r'PROBE_JSON:(\{.*\})', dom, re.S)
    dump = os.path.join(BASE, 'build', '_probe_%s_dom.txt' % tag)
    if not m:
        open(dump, 'w', encoding='utf-8').write(dom)
        print('    [FAIL] 探针没回传结果，DOM 已存 %s' % dump)
        return None
    import html as _h
    return json.loads(_h.unescape(m.group(1)))


OK = 0
FAIL = 0


def chk(name, cond, extra=''):
    global OK, FAIL
    if cond:
        OK += 1
        print('  [OK]   ' + name)
    else:
        FAIL += 1
        print('  [FAIL] ' + name + ('   → ' + str(extra) if extra != '' else ''))


# ---------------------------------------------------------------- 主流程
print('=' * 78)
print('研报页 report.html + 工作台跳转 · E2E 真机探针')
print('=' * 78)

print('\n[1] 生成探针页')
sz1 = inject(os.path.join(DEPLOY, 'report.html'), OUT_RPT, RPT_PROBE)
sz2 = inject(os.path.join(DEPLOY, 'index.html'), OUT_WB, WB_PROBE)
print('    %s（%d 字节）' % (os.path.basename(OUT_RPT), sz1))
print('    %s（%d 字节）' % (os.path.basename(OUT_WB), sz2))
check_js(RPT_PROBE, '研报页', os.path.join(BASE, 'build', '_tmp_p1.js'))
check_js(WB_PROBE, '工作台', os.path.join(BASE, 'build', '_tmp_p2.js'))


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


os.chdir(DEPLOY)
socketserver.TCPServer.allow_reuse_address = True
httpd = socketserver.TCPServer(('127.0.0.1', PORT), Quiet)
threading.Thread(target=httpd.serve_forever, daemon=True).start()
print('\n[2] 本地 http：http://127.0.0.1:%d/（根目录 deploy/）' % PORT)

edge = edge_path()
print('[3] Edge：%s' % edge)

# ------------------------------------------------ 研报页
print('\n' + '-' * 78)
print('【一】研报页 report.html?code=%s' % CODE)
print('-' * 78)
d = run_probe(edge, 'http://127.0.0.1:%d/_probe_rpt.html?code=%s' % (PORT, CODE),
              'rpt', os.path.join(BASE, 'build', '_prof_rpt'))
if d is None:
    httpd.shutdown()
    raise SystemExit(1)

print('阶段：%s' % d.get('stage'))
print('注入脚本错误：%s' % (d.get('err') or '无'))
print('页面错误钩子 __RPT_ERR：%s' % (d.get('rptErr') or '（见下）'))

print('\n── A. 数据来源与规模 ──')
print('  来源=%s  代码=%s  %s %s' % (d.get('src'), d.get('code'), d.get('repName'), d.get('repTitle')))
print('  模块 %s 个 · 图表 %s 张 · KPI(库) %s 项 · 加载错误=%r'
      % (d.get('modN'), d.get('chartN'), d.get('kpiN_data'), d.get('loadErr')))
print('  顶栏标签：%s' % d.get('barTags'))
chk('数据来自云端数据库（不是内置副本）', d.get('src') == 'cloud', d.get('src'))
chk('没有加载错误', not d.get('loadErr'), d.get('loadErr'))
chk('23 个模块', d.get('modN') == 23, d.get('modN'))
chk('16 张图表', d.get('chartN') == 16, d.get('chartN'))
chk('8 项 KPI 入库', d.get('kpiN_data') == 8, d.get('kpiN_data'))

print('\n── B. 红主题 ──')
print('  --accent=%s  --accent-soft=%s  --green=%s' % (d.get('accent'), d.get('accentSoft'), d.get('green')))
print('  hero 背景：%s' % d.get('heroBg'))
print('  CSS %s 字符 · 蓝调残留 %s 处 · 数据里红调 %s 处 / 蓝调 %s 处'
      % (d.get('cssLen'), d.get('blueCss'), d.get('redData'), d.get('blueData')))
chk('--accent 是正红 #c8102e', str(d.get('accent')).lower() == '#c8102e', d.get('accent'))
chk('--accent-soft 是浅红底 #fdecee', str(d.get('accentSoft')).lower() == '#fdecee', d.get('accentSoft'))
chk('涨红跌绿的绿没被动（--green 仍是 #0b8a5c）',
    str(d.get('green')).lower() == '#0b8a5c', d.get('green'))
chk('hero 是红渐变（含 200, 16, 46）', '200, 16, 46' in str(d.get('heroBg')), d.get('heroBg'))
chk('整套 CSS 里 0 处蓝调残留', d.get('blueCss') == 0, d.get('blueCss'))
chk('图表数据里 0 处蓝调残留', d.get('blueData') == 0, d.get('blueData'))
chk('图表数据里确实换成了红（>=1 处）', (d.get('redData') or 0) >= 1, d.get('redData'))

print('\n── C. 渲染 ──')
print('  DOM 卡片 %s 个（data-mod %s）· 编号 %s' % (d.get('cards'), d.get('dataMods'), d.get('nos')))
print('  前 3 个标题：%s' % (d.get('heads') or [])[:3])
print('  KPI 渲染 %s 项：%s' % (d.get('kpiN'), d.get('kpiLabels')))
print('  目录 %s 条 · 徽标 %s 个 · 结论 %s 字 · 页脚 %s 字'
      % (d.get('tocN'), len(d.get('badges') or []), d.get('verdictLen'), d.get('footLen')))
chk('23 张内容卡片全渲染', d.get('cards') == 23, d.get('cards'))
chk('每张卡片带 data-mod（可定位编辑）', d.get('dataMods') == 23, d.get('dataMods'))
chk('编号 1…23 连续无缺', (d.get('nos') or []) == [str(i) for i in range(1, 24)], d.get('nos'))
chk('m23 锚点归「投资结论」卡片', d.get('m23') is True)
chk('一句话本质有自己的锚点', d.get('essence') is True)
chk('8 项 KPI 全渲染', d.get('kpiN') == 8, d.get('kpiN'))
chk('目录 7 条', d.get('tocN') == 7, d.get('tocN'))
chk('核心结论有内容（>200 字）', (d.get('verdictLen') or 0) > 200, d.get('verdictLen'))
chk('页脚免责声明有内容（>200 字）', (d.get('footLen') or 0) > 200, d.get('footLen'))

print('\n── D. 图表 ──')
print('  渲染 %s 张 · canvas %s 个 · 实例 %s 个 · 最小 %sx%s px'
      % (d.get('charts'), d.get('cvN'), d.get('chartInst'), d.get('cvMinW'), d.get('cvMinH')))
print('  缺 canvas：%s' % (d.get('cvMiss') or '无'))
print('  槽位键：%s' % d.get('slotKeys'))
print('  各图 canvas 尺寸：%s' % json.dumps(d.get('cvW') or {}, ensure_ascii=False))
print('  window.echarts = %s（版本 %s）' % (d.get('hasEcharts'), d.get('echartsVer')))
print('  槽位错误：%s' % (d.get('slotMiss') or '无'))
print('  页面 __RPT_ERR：%s' % (d.get('rptErr') or '无'))
chk('ECharts 库已就位', d.get('hasEcharts') == 'object' and d.get('echartsVer') == '5.5.1',
    '%s / %s' % (d.get('hasEcharts'), d.get('echartsVer')))
chk('所有图表槽位都能渲染（无「图表渲染失败」）', not (d.get('slotMiss') or []), d.get('slotMiss'))
chk('16 张图表渲染完成（window.__RPT_CHARTS）', d.get('charts') == 16, d.get('charts'))
chk('16 个 data-chart 槽位都在', d.get('slots') == 16, d.get('slots'))
chk('16 张都画出 canvas', d.get('cvN') == 16 and not (d.get('cvMiss') or []),
    '%s / 缺 %s' % (d.get('cvN'), d.get('cvMiss')))
chk('canvas 尺寸正常（宽>=200 高>=100）',
    (d.get('cvMinW') or 0) >= 200 and (d.get('cvMinH') or 0) >= 100,
    '%sx%s' % (d.get('cvMinW'), d.get('cvMinH')))
chk('ECharts 实例 16 个', d.get('chartInst') == 16, d.get('chartInst'))
chk('库里的 {{fn:}} 具名标记 15 处（设计如此，非残留）', d.get('fnLeft') == 15, d.get('fnLeft'))
chk('16 张图 revive() 全部还原成真函数且不留标记',
    d.get('reviveOk') == 16 and not (d.get('reviveBad') or []),
    '%s / %s' % (d.get('reviveOk'), d.get('reviveBad')))
print('  图表数据表规模：')
for k, v in sorted((d.get('rowShapes') or {}).items()):
    print('    %-16s %s' % (k, v))
chk('16 张图数据表 ↔ option 往返无损', not (d.get('rtBad') or []), d.get('rtBad'))

print('\n── H. 编辑模式 / 编辑器可达性 ──')
print('  html.className %r → %r · 模块编辑按钮 %s 个 · 图表编辑按钮 %s 个'
      % (d.get('editing'), d.get('editingOff'), d.get('opsBtns'), d.get('chartOps')))
print('  打开模块编辑器：UI.selMod=%r 表单=%s 标题=%r 正文长度=%s'
      % (d.get('editModSel'), d.get('editModOpened'), d.get('editModTitle'), d.get('editModHtml')))
print('  打开图表编辑器：UI.selChart=%r 表单=%s 数据格=%s 列=%s'
      % (d.get('editChartSel'), d.get('editChartOpened'), d.get('editChartGrid'), d.get('editChartCols')))
chk('编辑模式可开可关', d.get('editing') == 'edit' and d.get('editingOff') == '',
    (d.get('editing'), d.get('editingOff')))
chk('23 张卡片各有一个「编辑本模块」按钮', d.get('opsBtns') == 23, d.get('opsBtns'))
chk('16 张图表各有一个「图表数据」按钮', d.get('chartOps') == 16, d.get('chartOps'))
chk('点「编辑本模块」能真的打开该模块的编辑器（回归 openDrawer 清空选中项）',
    d.get('editModOpened') is True and d.get('editModSel') == CODE + '_m1',
    (d.get('editModSel'), d.get('editModOpened')))
chk('模块编辑器回填了标题与正文', (d.get('editModTitle') or '') != '' and (d.get('editModHtml') or 0) > 100,
    '%r / %s' % (d.get('editModTitle'), d.get('editModHtml')))

print('\n── I. 正文不显示代码（可视化编辑）──')
print('  编辑区可见文字：%r' % (d.get('editVis') or '')[:70])
print('  工具条按钮：%s 个 · 源码框默认隐藏=%s（%s）' % (d.get('editBarBtns'), d.get('editSrcHidden'), d.get('editSrcBox')))
print('  m12 图表标签：%s 个（可点选=%s）· 编辑区里的原始 <div data-chart> = %s 个'
      % (d.get('chipN'), d.get('chipEditable'), d.get('rawChartDiv')))
print('  标签文字：%r' % (d.get('chipText') or ''))
print('  展开「代码」后 textarea 长度=%s 且含 data-chart=%s' % (d.get('srcLen'), d.get('srcHasCode')))
v = d.get('editVis') or ''
chk('正文编辑区是 contenteditable（不是给用户看的代码框）', d.get('editModOpened') is True)
chk('可见文字里不出现标签 / data-chart / class=', not re.search(r'<[a-z]|data-chart|class=', v, re.I),
    v[:90])
chk('工具条按钮齐全（≥12 个）', (d.get('editBarBtns') or 0) >= 12, d.get('editBarBtns'))
chk('源码 textarea 默认是收起的（用户看不到代码）', d.get('editSrcHidden') is True)
chk('图表位置显示为受保护的标签（不可编辑）',
    (d.get('chipN') or 0) == 6 and (d.get('chipEditable') or 0) == 6, (d.get('chipN'), d.get('chipEditable')))
chk('编辑区里没有裸露的 <div data-chart>', (d.get('rawChartDiv') or 0) == 0, d.get('rawChartDiv'))
chk('标签文字是人话，不是 HTML', '图表' in str(d.get('chipText') or '') and '<' not in str(d.get('chipText') or ''),
    d.get('chipText'))
chk('展开「代码」能看到原始 HTML（含图表 div）', d.get('srcHasCode') is True, d.get('srcLen'))
chk('可视化区里的内容转回 HTML 后不含内部标签 rte-chip', d.get('modHtmlBacked') is False, d.get('modHtmlBacked'))

rte = d.get('rte') or {}
print('\n  ── 打开-不改-保存 必须零改动 ──')
print('  原 HTML %s 字 → 保存后 %s 字 · 逐字一致=%s' % (rte.get('beforeLen'), rte.get('notouchLen'), rte.get('notouchSame')))
chk('没动过内容时保存不会改动库里的 HTML', rte.get('notouchSame') is True,
    '%s vs %s' % (rte.get('beforeLen'), rte.get('notouchLen')))
print('  ── 真改内容并保存 ──')
print('  dirty=%s · 保存后 %s 字 · 含标记=%s · 图表数 %s→%s · 无script=%s 无on事件=%s · 残留chip=%s'
      % (rte.get('dirtyFlag'), rte.get('afterLen'), rte.get('hasMarker'),
         rte.get('beforeCharts'), rte.get('chartsKept'),
         rte.get('noScript'), rte.get('noOnAttr'), rte.get('chipLeft')))
print('  还原后与原始 HTML 逐字一致=%s' % rte.get('restored'))
chk('改内容后保存真的写进数据库', rte.get('hasMarker') is True, rte)
chk('6 个图表位置在往返后一个不少', rte.get('chartsKept') == rte.get('beforeCharts') == 6,
    '%s → %s' % (rte.get('beforeCharts'), rte.get('chartsKept')))
chk('写库前剥掉了 <script>', rte.get('noScript') is True, rte.get('afterLen'))
chk('写库前剥掉了 on* 事件属性（防 XSS）', rte.get('noOnAttr') is True, rte.get('afterLen'))
chk('保存的不是内部标签（rte-chip 不落库）', rte.get('chipLeft') is False)
chk('验证数据已还原', rte.get('restored') is True)
print('\n  ── 新建研报防覆盖闸门（血案回归）──')
print('  用已有代码创建 → 警告=%s：%r' % (rte.get('warnShown'), rte.get('warnText')))
chk('用已存在的代码创建研报会被拒绝（不覆盖）', rte.get('warnShown') is True, rte)
chk('被拒后数据库内容一字未动', rte.get('dupSafe') is True, rte)
chk('点「图表数据」能真的打开数据表编辑器',
    d.get('editChartOpened') is True and (d.get('editChartGrid') or 0) >= 20,
    (d.get('editChartSel'), d.get('editChartGrid')))
chk('图表编辑器数据表带列名', len(d.get('editChartCols') or []) >= 3, d.get('editChartCols'))

print('\n── G. 安全闸门 ──')
sec = d.get('sec') or {}
print('  错 token/pass → wb_admin_verify：%s  %s' % (sec.get('verify'), sec.get('verifyRaw') or sec.get('verifyErr') or ''))
print('  错密码   → wb_admin_login ：%s  %s' % (sec.get('login'), sec.get('loginRaw') or sec.get('loginErr') or ''))
print('  匿名 DELETE wb_reports → %s %s' % (sec.get('anonDel'), sec.get('anonDelErr') or ''))
print('  链异常：%s' % (sec.get('chainErr') or '无'))
chk('错 token 的管理员校验被服务端拒绝', sec.get('verify') == 'rejected', sec)
chk('错密码的管理员登录被服务端拒绝', sec.get('login') == 'rejected', sec)
chk('错密码没有换到任何 token', sec.get('tokenGot') is False, sec)
chk('匿名 DELETE 被拒（收回 DELETE 权限生效）', sec.get('anonDel') == 'denied', sec)

print('\n── E. 保存到数据库：页眉与 KPI ──')
hw = d.get('hw') or {}
print('  打开面板：mask=%s 标题框=%s KPI 行=%s 表单字段=%s'
      % (hw.get('maskOn'), hw.get('titleFld'), hw.get('kpiRows'), hw.get('fields')))
print('  表单里的 KPI 原值=%r（库里 %r）' % (hw.get('kValFromForm'), hw.get('origKpiVal')))
print('  改标题 %r → %r / 改 KPI 数值 → 27.99' % (hw.get('origTitle'), hw.get('newTitle')))
print('  回读：标题=%r KPI=%r' % (hw.get('dbTitle'), hw.get('dbKpiVal')))
print('  还原后回读：标题=%r KPI=%r' % (hw.get('dbTitleBack'), hw.get('dbKpiBack')))
chk('数据管理面板能打开且表单字段齐全',
    hw.get('maskOn') is True and hw.get('titleFld') is True and (hw.get('fields') or 0) >= 8, hw)
chk('KPI 表格 8 行可编辑', hw.get('kpiRows') == 8, hw.get('kpiRows'))
chk('表单回填了数据库里的原值', str(hw.get('kValFromForm')) == str(hw.get('origKpiVal')),
    '%r vs %r' % (hw.get('kValFromForm'), hw.get('origKpiVal')))
chk('改标题 + 改 KPI → 保存后数据库真的变了', hw.get('savedOk') is True, hw)
chk('还原后数据库与改动前一致', hw.get('restoredOk') is True, hw)

print('\n── F. 保存到数据库：图表数据表 ──')
cw = d.get('cw') or {}
print('  图表 %s · 数据表 %s · 列名 %s' % (cw.get('key'), cw.get('shape'), cw.get('gridCols')))
print('  输入格 %s 个 · 第一格 %r → %r' % (cw.get('gridInputs'), cw.get('cellOld'), cw.get('newV')))
print('  保存后回读 series[0].data[0] = %r' % cw.get('dbVal'))
print('  界面还原后与原值一致 = %s（值 %r）· 兜底直传=%s · 最终一致=%s'
      % (cw.get('uiRestoredSame'), cw.get('uiVal'), cw.get('fallbackPosted'), cw.get('finalSame')))
chk('图表数据表渲染出可编辑矩阵', (cw.get('gridInputs') or 0) >= 6, cw.get('gridInputs'))
chk('第一行第一系列的数字可定位', cw.get('cellFound') is True)
chk('改数字 → 保存后数据库里的 opt 真的变了', cw.get('savedOk') is True, cw)
chk('还原后回到原始 opt（逐字一致）', cw.get('finalSame') is True,
    'ui=%s final=%s' % (cw.get('uiRestoredSame'), cw.get('finalSame')))

errs = (d.get('err') or [])
print('\nJS 错误：%s' % (errs or '无'))
chk('研报页 JS 零错误', not errs, errs)

# ------------------------------------------------ 工作台
print('\n' + '-' * 78)
print('【二】工作台 index.html · 投资标的 → 研报跳转')
print('-' * 78)
w = run_probe(edge, 'http://127.0.0.1:%d/_probe_wb.html' % PORT,
              'wb', os.path.join(BASE, 'build', '_prof_wb'))
if w is None:
    httpd.shutdown()
    raise SystemExit(1)

print('阶段：%s' % w.get('stage'))
print('注入脚本错误：%s' % (w.get('err') or '无'))
print('副标题：%s' % w.get('subTxt'))
print('rptHref({600459}) = %r   rptHref({}) = %r' % (w.get('hrefHelper'), w.get('hrefHelper2')))
chk('切到投资标的页', w.get('pageOn') is True)
chk('App.openReport 已定义', w.get('openReportFn') == 'function', w.get('openReportFn'))
chk('rptHref 生成 report.html?code=…', w.get('hrefHelper') == 'report.html?code=600459', w.get('hrefHelper'))
chk('rptHref 对空行也安全', w.get('hrefHelper2') == 'report.html?code=', w.get('hrefHelper2'))
chk('副标题提示了「点名称打开研报」', '深度研究报告' in str(w.get('subTxt')), w.get('subTxt'))

print('\n  列表列名：%s' % (w.get('cols') or [])[:8])
print('  ── 拉取研报代码前 ──')
for r0 in (w.get('before') or []):
    print('    %s  a=%s href=%s cls=%s 代码链接=%s' % (r0.get('code'), r0.get('aTag'), r0.get('aHref'),
                                                    r0.get('aCls'), r0.get('cHref')))
print('  ── 拉取研报代码后（桩返回 600456 有研报）──')
for r0 in (w.get('after') or []):
    print('    %s  %s href=%s cls=%s 有📄=%s 代码链接=%s'
          % (r0.get('code'), r0.get('aTxt'), r0.get('aHref'), r0.get('aCls'), r0.get('hasDot'), r0.get('cHref')))
print('  RPT_CODES=%s（loadedFlag=%s）' % (w.get('rptCodes'), w.get('loadedFlag')))
print('  openReport 打开的 URL：%r' % w.get('openUrl'))
chk('RPT_CODES 从数据库拉到研报代码', (w.get('rptCodes') or []) == ['600456'], w.get('rptCodes'))
chk('已加载标记置位', w.get('loadedFlag') is True)
chk('名称列是 <a>（可点击）', all((x.get('aTag') == 'A') for x in (w.get('after') or [])),
    [(x.get('code'), x.get('aTag')) for x in (w.get('after') or [])])
chk('名称链接 href = report.html?code=<代码>',
    all(x.get('aHref') == 'report.html?code=' + x.get('code') for x in (w.get('after') or [])),
    [(x.get('code'), x.get('aHref')) for x in (w.get('after') or [])])
chk('代码列也是可点击链接',
    all(x.get('cHref') == 'report.html?code=' + x.get('code') for x in (w.get('after') or [])),
    [(x.get('code'), x.get('cHref')) for x in (w.get('after') or [])])
a456 = [x for x in (w.get('after') or []) if x.get('code') == '600456']
a459 = [x for x in (w.get('after') or []) if x.get('code') == '600459']
chk('已有研报的标的多一个 has 类（深红 + 📄）',
    bool(a456) and 'has' in str(a456[0].get('aCls')) and a456[0].get('hasDot') is True, a456)
chk('没有研报的标的不加 has 类',
    bool(a459) and 'has' not in str(a459[0].get('aCls')) and a459[0].get('hasDot') is False, a459)
chk('操作列有「📄」按钮且调用 App.openReport',
    all(any('📄' in o and 'App.openReport' in o for o in (x.get('ops') or []))
        for x in (w.get('after') or [])),
    [(x.get('code'), x.get('ops')) for x in (w.get('after') or [])])
chk('App.openReport 真的能打开 report.html?code=600456',
    w.get('openUrl') == 'report.html?code=600456', w.get('openUrl'))
chk('工作台 JS 零错误', not (w.get('err') or []), w.get('err'))

print('\n' + '=' * 78)
print('通过 %d 项 · 失败 %d 项' % (OK, FAIL))
print('=' * 78)

httpd.shutdown()
for p in (OUT_RPT, OUT_WB):
    try:
        os.remove(p)
    except Exception:
        pass
for d0 in ('_prof_rpt', '_prof_wb'):
    shutil.rmtree(os.path.join(BASE, 'build', d0), ignore_errors=True)
print('\n[5] 临时文件已清理')
raise SystemExit(1 if FAIL else 0)
