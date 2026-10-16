#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""「回忆录」E2E 探针（本机模式）。

★ 本机模式：把 memoir.html 里的 `var DEV_MODE = false;` 改成 true，
  再用 `<body>` 后置脚本清空 localStorage 三个键 —— 一张生产表都不写。

覆盖：
  0. 页面形态：本机模式徽标、三栏 DOM、零外部依赖
  1. 新建笔记（点真实按钮 .rnew）→ 卡片数 +1、编辑器就位
  2. 改标题 / 正文 → 自动保存（1.2s 防抖）→ 卡片与 localStorage 同步
  3. 富文本：局选字号 / 加粗 / 字体色 / 高亮 → 产物是带 style 的 span（且过白名单）
  4. 标记颜色：弹层选色 → 圆点与卡片色条跟着变
  5. 笔记本：新建 → 左栏出现、右侧徽标显示笔记归属
  6. 标签：输入 + Enter → chip 与左栏标签区同步；点 ✕ 删除
  7. 置顶：按钮态 + 「置顶」视图能筛到
  8. 搜索：输入关键词 → 列表只剩匹配项
  9. 回收站：软删 → 全部视图消失 / 回收站出现 → 还原
 10. 彻底删除：密码弹层 → 确认后 NOTES 里彻底没有
 11. 清空回收站：批量走通（本机模式）
 12. 导出：单文件 HTML / 全量 JSON 备份（拦下 a.click 收 download 名）
 13. 清洗器：<script> / onerror / javascript: 全被剥掉
 14. 全程零 JS 错误

跑法：
  /Users/luoshui/.workbuddy/binaries/python/envs/default/bin/python build/probe_memoir_e2e.py
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
ROOT = os.path.dirname(HERE)
SRC_PAGE = os.path.join(ROOT, 'deploy', 'memoir.html')
LIVE_URL = 'https://liuchaowang.cn/memoir.html'
SITE = os.path.join(HERE, '_mem_site')          # 独立临时目录：绝不碰 deploy_site/
PAGE = 'memoir.html'
PROBE_PAGE = '_e2e_memoir.html'
PORT = 8831
EDGE = '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge'
RESULT = []

DBG = r'''
<script>
(function(){
  var errs = [], out = [];
  window.addEventListener('error', function(e){ errs.push('ERR: ' + e.message); });
  window.addEventListener('unhandledrejection', function(e){
    errs.push('REJ: ' + ((e.reason && e.reason.message) || e.reason));
  });
  /* 拦下下载：不产生真实文件，只记账 */
  window.__DL = [];
  try{
    HTMLAnchorElement.prototype.click = function(){ window.__DL.push(String(this.download || this.href || '')); };
  }catch(e){}
  URL.createObjectURL = function(){ return 'blob:probe'; };
  URL.revokeObjectURL = function(){};

  function log(k, v){ out.push(k + ' = ' + v); }
  function sec(t){ out.push(''); out.push('=== ' + t + ' ==='); }
  function id(i){ return document.getElementById(i); }
  function txt(el){ return el ? (el.textContent || '').replace(/\s+/g, ' ').trim() : '(null)'; }
  function click(el){ if(!el){ out.push('✗ 找不到元素'); return false; } el.click(); return true; }
  function clickId(i){ return click(id(i)); }
  function sleep(ms){ return new Promise(function(r){ setTimeout(r, ms); }); }
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
  function setVal(el, v, ev){
    if(!el) return false;
    el.value = v;
    el.dispatchEvent(new Event(ev || 'input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
    return true;
  }
  function qa(sel){ return Array.prototype.slice.call(document.querySelectorAll(sel)); }
  function cardIds(){ return qa('#cards .card').map(function(c){ return c.getAttribute('data-id'); }); }
  function cardTitles(){ return qa('#cards .card .ttl').map(txt); }
  function bodyHtml(){ return id('ebody') ? id('ebody').innerHTML : ''; }
  function pick(root, sel){ return root.querySelector(sel); }
  /* 在 #ebody 里选中第一段文字 */
  function selectFirst(){
    var b = id('ebody');
    b.focus();
    var node = b.querySelector('div, p') || b.firstChild;
    if(!node) return false;
    while(node.firstChild) node = node.firstChild;
    var r = document.createRange();
    r.setStart(node, 0); r.setEnd(node, Math.min(4, node.length || 4));
    var s = window.getSelection(); s.removeAllRanges(); s.addRange(r);
    return true;
  }
  async function openDD(sel, btnSel){
    var dd = document.querySelector(sel);
    if(!dd) return false;
    var b = dd.querySelector('button');
    if(!b) return false;
    b.click();
    return dd.classList.contains('open');
  }

  (async function(){
    try{
      /* ★ 探针脚本在解析期就开跑，比 DOMContentLoaded 上的 boot() 还早 ——
         必须先等 boot 走完（DEV_MODE → 本机模式 + 欢迎稿），否则后面全是竞态。 */
      await waitFor(function(){ return UI.mode === 'local' && NOTES.length > 0; },
                    8000, 'boot 完成（本机模式）');

      /* ============ 0. 页面形态 ============ */
      sec('0. 页面形态（本机模式）');
      log('DEV_MODE', DEV_MODE);
      log('S.is_local / UI.mode', UI.mode);
      log('徽标', txt(id('modeBadge')));
      log('三栏 DOM（rail/lpane/epane）',
          [!!id('rail'), !!id('lpane'), !!id('epane')].join(' / '));
      log('外部依赖 script[src] / link 数',
          qa('script[src]').length + ' / ' + qa('link[rel=stylesheet]').length);
      log('起始笔记数', NOTES.length);
      log('起始笔记本数', BOOKS.length);
      log('欢迎稿标题', NOTES.length ? NOTES[0].title : '(无)');
      log('欢迎稿已自动打开', id('etitle') ? id('etitle').value : '(无编辑器)');
      log('启动后 JS 错误', errs.length ? errs.join(' | ') : '无');

      /* ============ 0.5 阅读模式 / 编辑模式 ============ */
      sec('0.5 打开即阅读模式，点「编辑」才可改');
      var tbDisp = function(){ return getComputedStyle(qa('.tbar')[0]).display; };
      log('默认 contenteditable', id('ebody').getAttribute('contenteditable'));
      log('默认 body.editing', document.body.classList.contains('editing'));
      log('默认工具条 display（应 none）', tbDisp());
      log('默认标题 readonly', id('etitle').hasAttribute('readonly'));
      log('默认按钮文案', txt(id('btnEdit')));
      log('默认正文 cursor', getComputedStyle(id('ebody')).cursor);
      var bodyBefore = (find(UI.cur) || {}).body;
      id('ebody').dispatchEvent(new Event('input', { bubbles: true }));
      await sleep(60);
      log('阅读模式下 input 不产生改动',
          (find(UI.cur) || {}).body === bodyBefore && UI.dirty === false);

      clickId('btnEdit');
      await sleep(80);
      log('点「编辑」后 contenteditable', id('ebody').getAttribute('contenteditable'));
      log('点「编辑」后 body.editing', document.body.classList.contains('editing'));
      log('点「编辑」后工具条 display（应 flex）', tbDisp());
      log('点「编辑」后标题 readonly', id('etitle').hasAttribute('readonly'));
      log('点「编辑」后按钮文案', txt(id('btnEdit')));
      log('点「编辑」后保存状态（不该是「只读」）', txt(id('saveState')));
      log('光标已进正文或标题',
          document.activeElement === id('ebody') || document.activeElement === id('etitle'));

      clickId('btnEdit');                      /* ✓ 完成 → 回阅读模式 */
      await sleep(120);
      log('再点一次 → contenteditable', id('ebody').getAttribute('contenteditable'));
      log('再点一次 → body.editing', document.body.classList.contains('editing'));
      log('再点一次 → 工具条 display', tbDisp());
      log('再点一次 → 保存状态', txt(id('saveState')));

      /* ============ 0.6 左栏折叠 / 展开 ============ */
      sec('0.6 左栏右侧的展开 / 收起手柄');
      var railRight = function(){ return Math.round(id('rail').getBoundingClientRect().right); };
      var rfLeft = function(){ return Math.round(id('rf').getBoundingClientRect().left); };
      /* 手柄用 SVG chevron，方向靠 .closed 旋转 —— 不再有文字箭头可读 */
      var btRect = function(){ return id('rtoggle').getBoundingClientRect(); };
      var btDir = function(){ return id('rtoggle').classList.contains('closed') ? '▶ 向右(展开)' : '◀ 向左(收起)'; };
      var btIcon = function(){
        var sv = id('rtoggle').querySelector('svg.ic');
        if(!sv) return '(无 svg)';
        return sv.getAttribute('viewBox') + ' ' + getComputedStyle(sv).transform;
      };
      log('手柄在 DOM 里', !!id('rtoggle'));
      log('手柄是胶囊（竖向、圆角、居中）',
          JSON.stringify({w: Math.round(btRect().width), h: Math.round(btRect().height),
            radius: getComputedStyle(id('rtoggle')).borderTopRightRadius,
            cy: Math.round(btRect().top + btRect().height / 2),
            railCy: Math.round(id('rail').getBoundingClientRect().height / 2)}));
      log('初始 railhide', id('app').classList.contains('railhide'));
      log('初始箭头方向（应 ◀ 收起）', btDir());
      log('初始图标（应未旋转）', btIcon());
      log('初始 rail 右边界 / 手柄 left', railRight() + ' / ' + rfLeft());
      log('手柄宽度（细胶囊，不压列表）', Math.round(btRect().width));
      /* 真·几何判定：手柄矩形与列表标题矩形是否相交（原来只比 x，位置改成居中后无意义） */
      (function(){
        var a = btRect(), b = document.querySelector('#listTitle').getBoundingClientRect();
        var hit = !(a.right <= b.left || a.left >= b.right || a.bottom <= b.top || a.top >= b.bottom);
        log('手柄与列表标题不重叠', !hit);
      })();
      /* 悬停态在无头环境触发不了，直接读样式表里 .rtoggle:hover 的规则做校验 */
      (function(){
        var out = '(未找到)';
        for(var i = 0; i < document.styleSheets.length; i++){
          var rs = document.styleSheets[i].cssRules || [];
          for(var j = 0; j < rs.length; j++){
            if(rs[j].selectorText === '.rtoggle:hover'){
              out = 'color=' + rs[j].style.color + ', border-color=' + rs[j].style.borderColor;
            }
          }
        }
        log('悬停态样式（只换色不变形）', out);
      })();
      /* 胶囊是否会压到笔记卡片：折叠前后各量一次 */
      (function(){
        var a = id('rtoggle').getBoundingClientRect();
        var c = document.querySelector('#cards .card');
        if(!c){ log('卡片与手柄不重叠', '(当前无卡片)'); return; }
        var b = c.getBoundingClientRect();
        log('展开时卡片与手柄不重叠（卡片 left / 手柄 right）',
            Math.round(b.left) + ' / ' + Math.round(a.right) + ' → ' + Math.round(b.left - a.right));
      })();
      toggleRail();
      await sleep(520);
      log('收起后 railhide', id('app').classList.contains('railhide'));
      log('收起后箭头方向（应 ▶ 展开）', btDir());
      log('收起后图标已旋转', btIcon());
      log('收起后 rail 右边界（应 ≈0）', railRight());
      log('收起后手柄 left（应 ≈0）', rfLeft());
      log('收起状态已记忆', localStorage.getItem('wb_memoir_rail_v1'));
      log('列表仍在原位（lpane 左边界 ≈0）',
          Math.round(id('lpane').getBoundingClientRect().left));
      log('收起后给胶囊留的走道 padding-left（应 24px）',
          getComputedStyle(qa('#cards')[0]).paddingLeft);
      (function(){
        var a = id('rtoggle').getBoundingClientRect();
        var c = document.querySelector('#cards .card');
        if(!c){ log('收起后卡片与手柄不重叠', '(当前无卡片)'); return; }
        var b = c.getBoundingClientRect();
        log('收起后卡片与手柄不重叠（卡片 left / 手柄 right）',
            Math.round(b.left) + ' / ' + Math.round(a.right) + ' → ' + Math.round(b.left - a.right));
      })();
      toggleRail();
      await sleep(520);
      log('展开后 railhide', id('app').classList.contains('railhide'));
      log('展开后 rail 右边界（应 ≈264）', railRight());
      log('展开后箭头方向', btDir());
      log('展开后 title', id('rtoggle').title);

      /* ============ 1. 新建 ============ */
      sec('1. 新建笔记（点真实按钮）');
      var n0 = NOTES.length;
      click(document.querySelector('.rnew'));
      await sleep(120);
      log('NOTES 条数（应 ' + (n0 + 1) + '）', NOTES.length);
      log('列表卡片数', qa('#cards .card').length);
      log('编辑器已展开', id('eform').style.display);
      log('UI.cur', UI.cur ? '已选中' : '(空)');
      log('新建后直接进编辑态（contenteditable）', id('ebody').getAttribute('contenteditable'));
      log('新建后 body.editing', document.body.classList.contains('editing'));
      log('左侧「全部」计数', txt(id('stAll')));

      /* ============ 2. 改标题 / 正文 + 自动保存 ============ */
      sec('2. 标题 / 正文 → 自动保存（1.2s 防抖）');
      setVal(id('etitle'), '探针笔记甲');
      id('ebody').innerHTML = '<div>第一行：这是一段用来测试格式的文字。</div>';

      /* ---- 3. 富文本 ---- */
      sec('3. 富文本：局选字号 / 加粗 / 颜色 / 高亮');
      var selOk = selectFirst();
      log('已选中 4 个字符', selOk + ' / ' + String(window.getSelection()).slice(0, 12));
      if(await openDD('#ddSize')) { /* 面板开着 */ }
      var szBtns = qa('#ddpSize .it');
      log('字号选项数', szBtns.length);
      var b24 = szBtns.filter(function(b){ return /^24/.test(txt(b)); })[0];
      click(b24);
      log('正文含 font-size:24px', /font-size:\s*24px/.test(bodyHtml()));
      closeDDs();

      var s2 = String(window.getSelection());
      selectFirst();
      click(document.querySelector('.tb[data-cmd="bold"]'));
      log('正文含加粗（font-weight:bold|b|strong）',
          /font-weight:\s*(bold|700)|<b>|<strong>/i.test(bodyHtml()));
      log('加粗按钮态 on', !!document.querySelector('.tb[data-cmd="bold"].on'));

      selectFirst();
      await openDD('#ddColor');
      log('字体色色块数', qa('#ddpColor .sw').length);
      click(qa('#ddpColor .sw')[2]);
      log('正文含 color:#c0392b（或 rgb 等价）',
          /color:\s*(#c0392b|rgb\(192,\s*57,\s*43\))/i.test(bodyHtml()));
      closeDDs();

      selectFirst();
      await openDD('#ddHilite');
      log('高亮色块数', qa('#ddpHilite .sw').length);
      click(qa('#ddpHilite .sw')[0]);
      log('正文含 background-color', /background-color/i.test(bodyHtml()));
      closeDDs();

      log('段落样式下拉项数', qa('#ddpBlock .it').length);
      log('字体下拉项数', qa('#ddpFont .it').length);

      /* 白名单：素材里塞脏东西，落库前必须被剥
         ⚠️ 注入脚本里绝不能出现字面量的 script 结束标签：那会提前关掉本探针
            自己的 script 标签，整个探针静默失效（踩过一次）。一律拼出来。 */
      sec('13. HTML 清洗器');
      var SO = '<' + 'script>';
      var SC = '<' + '/script>';
      var dirty = '<div onclick="x()">A' + SO + 'bad()' + SC + '<img src=x onerror=alert(1)>' +
                  '<a href="javascript:alert(1)">l</a><b style="color:#c0392b">B</b></div>';
      var clean = sanitize(dirty);
      log('清洗后', clean.replace(/</g, '‹'));
      log('无 script 标签', clean.indexOf(SO) < 0 && clean.indexOf('‹script') < 0);
      log('无 onerror / onclick', !/on\w+\s*=/.test(clean));
      log('无 javascript:', clean.indexOf('javascript:') < 0);
      log('保留 style 白名单（color）', /color:\s*#c0392b/i.test(clean));

      /* 回填正文并等自动保存 */
      id('ebody').innerHTML = '<div>第一行：这是一段用来测试格式的文字。</div>' +
                              '<div><span style="font-size:24px;color:#c0392b">大号红字</span></div>';
      id('ebody').dispatchEvent(new Event('input', { bubbles: true }));
      await sleep(1600);
      log('保存状态', txt(id('saveState')));
      log('卡片标题已同步', cardTitles().indexOf('探针笔记甲') >= 0);
      var myCard = document.querySelector('#cards .card[data-id="' + UI.cur + '"]');
      log('卡片摘要已同步', myCard ? txt(myCard.querySelector('.ex')).slice(0, 12) : '(无卡片)');
      log('字数统计', txt(id('wordStat')));
      var lsNotes = [];
      try{ lsNotes = JSON.parse(localStorage.getItem('wb_memoir_v1') || '[]'); }catch(e){}
      var saved = lsNotes.filter(function(x){ return x.title === '探针笔记甲'; })[0];
      log('localStorage 已落库', !!saved);
      log('落库正文已过白名单', saved ? (/font-size/.test(saved.body) && saved.body.indexOf('<script') < 0) : false);

      /* ============ 4. 标记颜色 ============ */
      sec('4. 标记颜色（弹层选色）');
      clickId('edot');
      log('弹层已开', id('mask').classList.contains('on'));
      log('色块数（9 = 无标记 + 8 色）', qa('#dlg .pal .sw').length);
      click(qa('#dlg .pal .sw')[1]);
      await sleep(80);
      log('弹层已关', !id('mask').classList.contains('on'));
      log('圆点背景', id('edot').style.background);
      var curCard = document.querySelector('#cards .card[data-id="' + UI.cur + '"]');
      log('卡片色条 --lb', curCard ? curCard.style.getPropertyValue('--lb') : '(无卡片)');
      log('左侧「带标记」计数', txt(id('stMark')));

      /* ============ 5. 笔记本 ============ */
      sec('5. 笔记本：新建并归入');
      var bk0 = BOOKS.length;
      setVal(id('ebook'), '__new');
      await sleep(60);
      log('弹层已开（新建笔记本）', id('mask').classList.contains('on'));
      setVal(id('dlgIn'), '丙午年杂记');
      clickId('dlgOk');
      await sleep(120);
      log('BOOKS 条数', BOOKS.length + '（原 ' + bk0 + '）');
      log('笔记归属', (find(UI.cur) || {}).book);
      log('左栏出现该笔记本', txt(id('bookNav')).indexOf('丙午年杂记') >= 0);
      log('下拉当前值', id('ebook').value);

      /* ============ 6. 标签 ============ */
      sec('6. 标签：新建 / 删除');
      setVal(id('tagadd'), '记忆');
      id('tagadd').dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
      await sleep(80);
      log('笔记标签', JSON.stringify((find(UI.cur) || {}).tags || []));
      log('chip 数', qa('#etags .etag').length);
      log('左栏标签区', txt(id('tagNav')).slice(0, 40));
      click(document.querySelector('#etags .etag b'));
      await sleep(60);
      log('删除后标签', JSON.stringify((find(UI.cur) || {}).tags || []));

      /* ============ 7. 置顶 ============ */
      sec('7. 置顶');
      clickId('btnPin');
      await sleep(80);
      log('按钮态 on', id('btnPin').classList.contains('on'));
      log('笔记 pin', (find(UI.cur) || {}).pin);
      setView('pin');
      await sleep(60);
      log('置顶视图能筛到', cardTitles().length > 0 && cardTitles().indexOf('探针笔记甲') >= 0);
      log('视图标题', txt(id('listTitle')));
      setView('all');
      await sleep(60);

      /* ============ 8. 搜索 ============ */
      sec('8. 搜索');
      var allN = cardTitles().length;
      setVal(id('q'), '探针笔记甲');
      await sleep(80);
      log('全部 ' + allN + ' 篇 → 命中', cardTitles().length);
      log('列表副标题', txt(id('listSub')));
      setVal(id('q'), 'zzz绝不存在zzz');
      await sleep(80);
      log('无结果空态', txt(id('cards')).slice(0, 20));
      setVal(id('q'), '');
      clickId('qclr');
      await sleep(80);
      log('清空后恢复', cardTitles().length);

      /* ============ 9. 回收站 ============ */
      sec('9. 回收站：软删 → 还原');
      var target = UI.cur;
      var nBefore = NOTES.filter(function(n){ return !n.is_del; }).length;
      clickId('btnDel');                       /* → 确认弹层 */
      await sleep(60);
      log('确认弹层已开', id('mask').classList.contains('on'));
      log('弹层标题', txt(id('dlg').querySelector('h3')));
      clickId('dlgOk');
      await sleep(150);
      log('存活笔记数（应 ' + (nBefore - 1) + '）', NOTES.filter(function(n){ return !n.is_del; }).length);
      log('回收站计数', txt(id('stTrash')));
      log('全部视图里已消失', cardIds().indexOf(target) < 0);
      setView('trash');
      await sleep(80);
      log('回收站视图标题', txt(id('listTitle')));
      log('回收站里有它', cardIds().indexOf(target) >= 0);
      log('清空按钮在', txt(id('cards')).indexOf('清空回收站') >= 0);
      click(document.querySelector('#cards .card .acts button'));   /* ↩ 还原 */
      await sleep(150);
      log('还原后 is_del', (find(target) || {}).is_del);
      setView('all');
      await sleep(80);

      /* ============ 12. 导出（先做，避免笔记被删掉） ============ */
      sec('12. 导出');
      window.__DL.length = 0;
      openNote(target);
      await sleep(120);
      log('重开一篇 → 回到阅读模式', id('ebody').getAttribute('contenteditable') +
          ' / editing=' + document.body.classList.contains('editing'));
      var exBtn = qa('.ehead .ebtn').filter(function(b){ return txt(b) === '⬇'; })[0];
      click(exBtn);
      await sleep(80);
      var bkBtn = qa('.rfoot button').filter(function(b){ return txt(b) === '备份'; })[0];
      click(bkBtn);
      await sleep(80);
      log('download 次数（应 2）', window.__DL.length);
      log('导出文件名', window.__DL.join(' / '));

      /* ============ 10. 彻底删除 ============ */
      sec('10. 彻底删除（本机模式免密码）');
      var n2 = NOTES.length;
      softDelete(target);
      await sleep(120);
      purgeNote(target);
      await sleep(80);
      log('密码弹层已开', id('mask').classList.contains('on'));
      log('弹层标题', txt(id('dlg').querySelector('h3')));
      setVal(id('dlgPw'), '981208');
      clickId('dlgOk');
      await sleep(200);
      log('NOTES 条数（应 ' + (n2 - 1) + '）', NOTES.length);
      log('目标已彻底不存在', !find(target));
      log('UI.cur 已清空', UI.cur === '');

      /* ============ 11. 清空回收站 ============ */
      sec('11. 清空回收站');
      var n3 = NOTES.length;
      var tmp = newNote();
      tmp.title = '待清空的垃圾';
      await sleep(60);
      softDelete(tmp.id);
      await sleep(120);
      log('回收站计数', txt(id('stTrash')));
      setView('trash');
      await sleep(80);
      click(qa('#cards .ebtn')[0]);
      await sleep(60);
      log('弹层已开', id('mask').classList.contains('on'));
      setVal(id('dlgPw'), '981208');
      clickId('dlgOk');
      await sleep(250);
      log('回收站计数（应 0）', txt(id('stTrash')));
      log('NOTES 条数（应 ' + (n3) + '）', NOTES.length);
      setView('all');

      /* ============ 14. 收尾 ============ */
      sec('14. 收尾');
      log('全程 JS 错误', errs.length ? errs.join(' | ') : '无');
      log('页脚统计', txt(id('footStat')));
      out.push('');
      out.push('__PROBE_END__');
    }catch(e){
      out.push('');
      out.push('✗ 探针异常：' + (e && e.message));
      out.push('__PROBE_END__');
    }
    try{
      await fetch('/', { method:'POST', body: out.join('\n') });
    }catch(e){}
  })();
})();
</script>
'''


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        n = int(self.headers.get('Content-Length') or 0)
        RESULT.append(self.rfile.read(n).decode('utf-8', 'replace'))
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
    del RESULT[:]
    cmd = [EDGE, '--headless=new', '--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage',
           '--window-size=1440,1200', url]
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
        try:
            p.kill()
        except Exception:
            pass
    return RESULT[0] if RESULT else '（%.0f 秒内没收到探针回传）' % timeout


def main(argv):
    live = '--live' in argv
    shutil.rmtree(SITE, ignore_errors=True)
    os.makedirs(SITE, exist_ok=True)
    print('=' * 78)
    print('「回忆录」E2E 探针（本机模式 · 不写任何生产表）')
    if live:
        print('★ --live：抓线上 %s 的真实字节来跑（验线上那一份，而不是本地构建产物）' % LIVE_URL)
    print('=' * 78)

    if live:
        import urllib.request
        req = urllib.request.Request(LIVE_URL, headers={'User-Agent': 'wb-probe'})
        raw = urllib.request.urlopen(req, timeout=40).read()
        print('线上字节 %d bytes' % len(raw))
        src = raw.decode('utf-8', 'replace')
    else:
        src = io.open(SRC_PAGE, encoding='utf-8').read()
    stripped, cnt = re.subn(r'var DEV_MODE = false;', 'var DEV_MODE = true;', src)
    assert cnt == 1, '未能切到 DEV_MODE（匹配 %d 次）' % cnt
    i = src.find('<body')
    j = src.find('>', i)
    pre = ('<script>try{localStorage.removeItem("wb_memoir_v1");'
           'localStorage.removeItem("wb_memoir_books_v1");'
           'localStorage.removeItem("wb_memoir_ui_v1");}catch(e){}</script>')
    page = stripped[:j + 1] + pre + stripped[j + 1:]
    io.open(os.path.join(SITE, PAGE), 'w', encoding='utf-8').write(page)
    # ⚠️ 必须用 rfind：页面自己的 printNote() 里有一个字面量的 </body></html>，
    #    用 replace(..., 1) 会把探针塞进那段 JS 字符串里 —— 探针静默失效（踩过）。
    k = page.rfind('</body>')
    assert k > 0, '找不到 </body>'
    io.open(os.path.join(SITE, PROBE_PAGE), 'w', encoding='utf-8').write(
        page[:k] + DBG + page[k:])

    srv = serve()
    res = run_probe('http://localhost:%d/%s' % (PORT, PROBE_PAGE), timeout=200)
    print(res)
    print('=' * 78)
    srv.shutdown()
    shutil.rmtree(SITE, ignore_errors=True)
    print('（已清理探针临时目录 %s）' % os.path.relpath(SITE, HERE))
    okEnd = '__PROBE_END__' in res
    bad = ('✗' in res) or ('全程 JS 错误 = 无' not in res) or (not okEnd)
    print('结论：' + ('✗ 有用例失败' if bad
                    else '✓ 全部通过（14 段%s）' % ('·线上字节' if live else '')))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
