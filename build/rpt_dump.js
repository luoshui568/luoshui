/* 用 Node 打桩 echarts / DOM，跑原始研报里的图表脚本，把每张图的 setOption 参数精确导出为 JSON。
   函数值统一序列化成 {{fn:<源码>}} 字符串，交由 Python 侧映射成具名标记。
   用法： node rpt_dump.js <源 HTML> <输出 JSON> */
const fs = require('fs');

const src = fs.readFileSync(process.argv[2], 'utf8');
const out = process.argv[3];

/* ---------- 打桩 ---------- */
function fakeEl(id) {
  const el = {
    id: id || '', style: {}, dataset: {}, className: '',
    classList: { add() {}, remove() {}, toggle() {}, contains() { return false; } },
    setAttribute() {}, getAttribute() { return null; },
    appendChild() {}, insertBefore() {}, removeChild() {},
    querySelector() { return null; }, querySelectorAll() { return []; },
    addEventListener() {}, closest() { return null; },
    getBoundingClientRect() { return { top: 0, left: 0, width: 600, height: 300 }; },
    clientWidth: 600, clientHeight: 300, scrollWidth: 600,
    innerHTML: '', textContent: '', value: ''
  };
  return el;
}
const captured = {};
const order = [];

global.window = {
  addEventListener() {}, removeEventListener() {},
  innerHeight: 900, innerWidth: 1400, devicePixelRatio: 1,
  requestAnimationFrame(fn) { return 0; },
  getComputedStyle() { return {}; }
};
global.IntersectionObserver = function (cb) {
  return { observe() {}, unobserve() {}, disconnect() {} };
};
global.requestAnimationFrame = function () { return 0; };
global.navigator = { userAgent: 'node' };
global.document = {
  documentElement: fakeEl('html'),
  body: fakeEl('body'),
  getElementById: function (id) { return fakeEl(id); },
  querySelector: function () { return null; },
  querySelectorAll: function () { return []; },
  createElement: function (t) { return fakeEl(t); },
  addEventListener() {}
};

function makeChart(id) {
  return {
    id: id,
    setOption(o) {
      captured[id] = o;
      if (order.indexOf(id) < 0) order.push(id);
      return this;
    },
    resize() {}, dispose() {}, dispatchAction() {},
    getOption() { return captured[id]; },
    on() {}, off() {}
  };
}
global.echarts = {
  init(el, theme) {
    const id = (el && el.id) ? el.id : String(el);
    return makeChart(id);
  },
  getInstanceByDom() { return undefined; },
  getInstanceById() { return undefined; },
  registerTheme() {},
  use() {},
  version: '5.5.1',
  graphic: {}, util: {}
};
global.window.echarts = global.echarts;   /* MI 图表脚本开头有 if(!window.echarts) return */

/* ---------- 抽取 <script> 块 ---------- */
const blocks = [];
const re = /<script[^>]*>([\s\S]*?)<\/script>/g;
let m;
while ((m = re.exec(src)) !== null) blocks.push(m[1]);
/* 第 1 块是 ECharts 库本体（~1MB），跳过 */
const codeBlocks = blocks.filter(b => !/^[\s\S]{0,400}Licensed to the Apache Software Foundation/.test(b.slice(0, 4000)));
const errs = [];
codeBlocks.forEach((b, i) => {
  try {
    (0, eval)('(function(){' + b + '\n})()');
  } catch (e) {
    errs.push('block#' + i + ': ' + e.message);
  }
});

/* ---------- 序列化（函数 → {{fn:源码}}） ---------- */
const ser = JSON.stringify(captured, function (k, v) {
  if (typeof v === 'function') return '{{fn:' + String(v).replace(/\s+/g, ' ').trim() + '}}';
  if (typeof v === 'number' && !isFinite(v)) return null;
  return v;
}, 1);

fs.writeFileSync(out, JSON.stringify({
  order: order,
  errs: errs,
  blocks: codeBlocks.length,
  opts: JSON.parse(ser)
}, null, 1), 'utf8');

/* 顺手把出现过的函数源码去重打印，便于人工建立映射 */
const fns = new Set();
(function walk(v) {
  if (v === null || v === undefined) return;
  if (typeof v === 'string') { const g = /\{\{fn:([\s\S]*?)\}\}/g; let x; while ((x = g.exec(v)) !== null) fns.add(x[1]); return; }
  if (Array.isArray(v)) { v.forEach(walk); return; }
  if (typeof v === 'object') { Object.keys(v).forEach(k => walk(v[k])); }
})(captured);
console.log('捕获图表 ' + order.length + ' 张：' + order.join(', '));
console.log('脚本块 ' + codeBlocks.length + ' 个，错误 ' + errs.length + ' 个' + (errs.length ? '：' + errs.join(' | ') : ''));
console.log('---- 函数源码（' + fns.size + ' 种）----');
Array.from(fns).sort().forEach(s => console.log('  ' + s));
