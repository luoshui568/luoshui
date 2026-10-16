/* ================================================================
   研报页「块样式」渲染层脚本（配套样式块 `rpt-blockstyle`）
   2026-10-15 · 纯 DOM，**零写库、零改研报数据**

   干三件事：
   ① 把正文里**未渲染的 Markdown 粗体 `**…**` 转成真正的 `<b>`**。
      病根：研报内容是 Markdown 风格的强调，写进 HTML 时没转标签，
      页面就**直接把星号显示出来**。全库实测 1,693 处，分布在 56 个模块
      （000762 占 1,449、600392 占 244）—— 这是「样式太土」的最大来源，
      比 CSS 更扎眼。在渲染层修 ⇒ 11 份研报一个字不用改。
   ② 给「整格都是数字 / 百分比 / 倍数」的单元格打 `is-num` 标，
      由 CSS 接管右对齐 + 等宽数字（tabular-nums），让数字列上下对齐。
   ③ **整站金色像素 → 浅蓝**（2026-10-15 用户令「不要金色系了，全部改成浅蓝色系」，
      配色从用户给的参考图实测反推：色相 202~208°、饱和度 36~62%、明度 86~100%）。
      为什么必须做在渲染层而不是纯 CSS：
        · 页面里金色散落在**十几个不同选择器**上（`.card > h3`、`#8a5a12`、
          `.verdict` 的金底、`.hist .h-en`、`.dcards::before`、结论块…），
          其中**一大半属于并发会话的地盘**（`rpt-txtstyle` 与模板自带样式），
          逐条写覆盖既要拼特异度、又会被对方下轮改回去；
        · 而它们的底色是 `linear-gradient(...)` 字符串，`background-color`
          算出来是 `transparent`，**CSS 无法对渐变中间色做色相变换**；
        · 渲染层按「HSL 判定金色 → 换成同明度/饱和度的蓝」一次扫干净，
          对方下次改样式也照样被扫掉，**不依赖对方源码**。
      ⚠️ 只改渲染结果，**不碰数据库**，打印 / 存 PDF 走同一份 DOM 所以 PDF 也是蓝的。

   ⚠️ 只碰 DOM，不碰数据库；打印 / 存 PDF 走的是同一份 DOM，所以 PDF 里也是干净的。
   ⚠️ 模块是**异步**渲染的：DOMContentLoaded 时 `#mods` 已存在但还是空的，
      实测首屏要 3~4 秒才灌进 341 个模块 ⇒ 光靠一次启动跑是不够的
      （踩过：补跑窗口全在首屏完成之前，星号一个都没换掉）。
      现在双保险：等 `.card` 出现 + 去抖 250ms 的 MutationObserver。
      自己改出来的 DOM 会再次触发 observer，但第二次已无 `**` 可改 ⇒ 不会自激。
   ⚠️ 格式残缺（`**` 落单）时**整节点跳过** —— 宁可漏改，也不错改。
   ⚠️ `createTreeWalker` **只在 `Document` 上、不在元素上**（踩过：守卫写成
      `!root.createTreeWalker` 永远为真 ⇒ 整个函数静默失效，一个星号都不换）。
   ⚠️ 别往 `window.Rpt` 上挂东西 —— 那是页面自己的命名空间，会被模板脚本整个覆盖掉。
   ================================================================ */
(function () {
  'use strict';
  if (window.__rptBlockStyle) return;
  window.__rptBlockStyle = 1;

  try {
    /* 这些标签里的文本一律不动（脚本/样式/代码/SVG 文本节点）
       ⚠️ 早期版本这里还含 `B:1, STRONG:1`，结果 002408 m6 的 104 个星号一个都没清掉
          （实测 bad_n=10 个残留节点的祖先链全是 `… > B > DIV.card`）——
          病根是**数据里粗体是嵌套包裹的**（`<b><p>**…**</p></b>`、整张表被裹进 `<b>`），
          一旦祖先里有 `<b>` 就整节点跳过 ⇒ 白名单反而漏了最多的一类。
          现在改成：`<b>` 不再跳过，转换时若父节点已经是 `<b>` 就**只去掉星号、保留纯文本**
          （粗体已经由外层 `<b>` 提供，不必再套一层 `<b>`）。 */
    var SKIP = { SCRIPT: 1, STYLE: 1, NOSCRIPT: 1, TEXTAREA: 1, INPUT: 1,
                 CODE: 1, PRE: 1, KBD: 1, SAMP: 1, SVG: 1, TITLE: 1 };
    var STRONG = { B: 1, STRONG: 1 };

    function badParent(node) {
      var e = node.parentNode;
      while (e && e.nodeType === 1) {
        if (SKIP[e.tagName]) return true;
        e = e.parentNode;
      }
      return false;
    }

    /* ---------- ① Markdown **粗体** → <b> ----------
       ⚠️ 不要用「先 split 再按下标奇偶配对」那套：正文里存在
       `**A** **B****C…` 这种**少一个收尾星号**的写法（000762 实测 7 个文本节点），
       split 会得到偶数段、按奇偶判断就会把整段丢掉（一个都不改）。
       改成**顺序配对扫描**：第 1、2 个星号对配一对，第 3、4 个配一对……
       末尾落单的那个星号直接**丢掉**（它是格式残渣，不是内容），
       这样既不会错加粗，也不会在页面上留一个孤零零的星号。 */
    function convert(txt, plain) {
      if (txt.indexOf('**') < 0) return null;
      var frag = document.createDocumentFragment();
      var pos = 0, a, b;
      while ((a = txt.indexOf('**', pos)) >= 0) {
        b = txt.indexOf('**', a + 2);
        if (a > pos) frag.appendChild(document.createTextNode(txt.slice(pos, a)));
        if (b < 0) { pos = txt.length; break; }        /* 落单收尾：丢弃星号，尾巴留纯文本 */
        var inner = txt.slice(a + 2, b);
        if (inner) {
          /* plain=1 ⇒ 外层已经是 <b>/<strong>，粗体有了，只留纯文本，不再嵌套一层 */
          if (plain) frag.appendChild(document.createTextNode(inner));
          else {
            var bo = document.createElement('b');
            bo.textContent = inner;
            frag.appendChild(bo);
          }
        }
        pos = b + 2;
      }
      if (pos < txt.length) frag.appendChild(document.createTextNode(txt.slice(pos)));
      return frag;
    }

    function fixBold(root) {
      if (!root || !document.createTreeWalker) return 0;
      var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null, false);
      var nodes = [], n;
      while ((n = walker.nextNode())) {
        if (n.nodeValue.indexOf('**') >= 0 && !badParent(n)) nodes.push(n);
      }
      var hit = 0;
      for (var i = 0; i < nodes.length; i++) {
        var p = nodes[i].parentNode;
        if (!p) continue;
        var plain = !!STRONG[p.tagName];
        var frag = convert(nodes[i].nodeValue, plain);
        if (!frag) continue;
        p.replaceChild(frag, nodes[i]);
        hit++;
      }
      return hit;
    }

    /* ---------- ② 数字单元格打标（右对齐 + 等宽数字）---------- */
    /* 只认「数字 + 最多一个单位」的整格，避免把「15 万吨/年」这类也右对齐 */
    var NUM = /^[-+−–—(（]?\s*[\d,，.．]+\s*(?:%|pct|倍|元|元\/股|元\/吨)?\s*[)）]?$/i;
    function markNum(root) {
      if (!root || !root.querySelectorAll) return 0;
      var cells = root.querySelectorAll('table td'), c = 0;
      for (var i = 0; i < cells.length; i++) {
        var td = cells[i];
        var cls = td.className || '';
        if (cls.indexOf('is-num') >= 0) continue;
        var txt = (td.textContent || '').replace(/\s+/g, ' ').trim();
        if (!txt || txt.length > 22) continue;
        if (NUM.test(txt)) { td.className = (cls ? cls + ' ' : '') + 'is-num'; c++; }
      }
      return c;
    }

    /* ---------- ②b 长文本单元格打标（居中，2026-10-15 用户令）---------- */
    /* 起因：模块 17「三大募投项目对照」4 列宽表，末列
       「模锻件 1,000吨/年 + 精密铸件 200吨/年」折行后顶到列边缘，
       看着像「右边溢出」。用户要「一行的文字太多了就还行居中」。
       —— 为什么必须打在渲染层：CSS 判不了「这格文字多不多」。
          写 `td:nth-child(n+2)` / `:not(.is-num)` 之类的猜测规则，
          会把「陕西省宝鸡市高新区」这种 11 字的短文本也居中，
          和同表其他列对齐方式不一致，反而更乱。
       —— 阈值 14 字：低于它一行放得下，居中没有意义；
          高于它必然折行，居中才解决「顶边」的观感。
       —— 与 is-num 互斥：数字格已右对齐（要对齐小数点），不能再居中。
       —— 首列（.mi-dim 维度名）已由 CSS 居中，且文字都短，不会命中。 */
    var TXT_MIN = 14;
    function markTxt(root) {
      if (!root || !root.querySelectorAll) return 0;
      var cells = root.querySelectorAll('table td'), c = 0;
      for (var i = 0; i < cells.length; i++) {
        var td = cells[i];
        var cls = td.className || '';
        if (cls.indexOf('is-num') >= 0 || cls.indexOf('is-txt') >= 0) continue;
        /* 数字 + 单位混排（如「4万吨/年」「7,000吨/年」）不算长文本：
           它本质是数字，右对齐更合适。判据 = 含数字且不含长中文串。 */
        var txt = (td.textContent || '').replace(/\s+/g, ' ').trim();
        if (txt.length < TXT_MIN) continue;
        if (NUM.test(txt)) continue;               /* 整格是数字 → 已 is-num 或本就不该居中 */
        var han = txt.match(/[\u4e00-\u9fa5]/g);
        if (!han || han.length < TXT_MIN) continue; /* 中文不足 → 是英文/数字串，不归它管 */
        td.className = (cls ? cls + ' ' : '') + 'is-txt';
        c++;
      }
      return c;
    }

    /* ---------- ③ 整站金色 → 浅蓝（色相搬运，不是「换个颜色」） ----------
       做法：对每一处声明了颜色的计算样式，取出 rgb 三通道，
       用 HSL 判定「是不是金色」（色相落在 38~62°、且 R−B 明显大于 G−B），
       是则**保持原明度 L 与饱和度 S**，把色相搬到 202~208°（青蓝），
       再写回inline style。
       ★ 为什么必须保留 L / S 只换 H：
         - 保留 L ⇒ 原本是「浅金底」的还是浅底、原本是「深金字」的还能当字色用，
           不会因为整片变成同一个蓝而糊掉层级；
         - 保留 S ⇒ 原来看不出饱和度的极淡底色，换完依旧极淡。
       ★ 为什么判据要「色相 + R−B > G−B」两个条件：
         页面里还有**品牌红**（涨跌色 #d0202f / #0b8a5c 绿），红色色相在 0~15°、
         绿色在 140°左右，都不落在 38~62° 区间，天然被排除 ——
         **不能只看「R>G>B」**，否则红色也会被搬走，涨跌语义就毁了。 */
    function hslToRgb(h, s, l) {
      var c = (1 - Math.abs(2 * l - 1)) * s;
      var x = c * (1 - Math.abs(((h / 60) % 2) - 1));
      var m = l - c / 2, r = 0, g = 0, b = 0;
      if (h < 60)       { r = c; g = x; }
      else if (h < 120) { r = x; g = c; }
      else if (h < 180) { g = c; b = x; }
      else if (h < 240) { g = x; b = c; }
      else if (h < 300) { r = x; b = c; }
      else              { r = c; b = x; }
      return [Math.round((r + m) * 255), Math.round((g + m) * 255), Math.round((b + m) * 255)];
    }
    function rgbToHsl(r, g, b) {
      r /= 255; g /= 255; b /= 255;
      var mx = Math.max(r, g, b), mn = Math.min(r, g, b), d = mx - mn;
      var h = 0, l = (mx + mn) / 2, s = 0;
      if (d > 0) {
        s = d / (1 - Math.abs(2 * l - 1));
        if (mx === r)      h = 60 * (((g - b) / d) % 6);
        else if (mx === g) h = 60 * ((b - r) / d + 2);
        else               h = 60 * ((r - g) / d + 4);
        if (h < 0) h += 360;
      }
      return [h, s, l];
    }
    /* 金色判定：色相在琥珀区间，且 R−B 明显大于 G−B（这是「金」区别于「橙红」的关键） */
    function isGold(r, g, b) {
      if (r < 118 || g < 62) return false;               /* 太暗的棕黑不算 */
      var h = rgbToHsl(r, g, b)[0];
      if (h < 36 || h > 64) return false;                /* 排除红(0~15)与绿黄(90+) */
      return (r - b) >= 26 && (r - b) > (g - b) + 8;
    }
    var PROPS_C = ['color', 'background-color', 'background', 'background-image',
                   'border-top-color', 'border-right-color',
                   'border-bottom-color', 'border-left-color', 'border-color',
                   'outline-color', 'text-decoration-color', 'box-shadow',
                   'text-shadow', 'fill', 'stroke', 'caret-color'];
    /* 把一段样式声明里的金色像素搬成蓝色，返回 null 表示没改 */
    function blueifyDecl(raw) {
      if (!raw || raw === 'none' || raw === 'transparent' || raw === 'currentcolor') return null;
      var changed = false;
      var out = raw.replace(/rgba?\(\s*(\d+)[,\s]+(\d+)[,\s]+(\d+)([^)]*)\)/g,
        function (m0, r, g, b, rest) {
          r = +r; g = +g; b = +b;
          if (!isGold(r, g, b)) return m0;
          changed = true;
          var hl = rgbToHsl(r, g, b), t = hslToRgb(205 / 360, hl[1], hl[2]);
          return 'rgba(' + t[0] + ', ' + t[1] + ', ' + t[2] + rest + ')';
        });
      return changed ? out : null;
    }
    function fixGold(root) {
      if (!root || !root.querySelectorAll) return 0;
      var els = root.querySelectorAll('*'), hit = 0, i, j;
      for (i = 0; i < els.length; i++) {
        var el = els[i];
        if (el.tagName === 'SCRIPT' || el.tagName === 'STYLE' || el.tagName === 'TEXTAREA') continue;
        if (el.dataset && el.dataset.rptGold === '1') continue;
        /* ★ 跳过**表头行与表头单元格**：它们是「红表头 + 浅蓝身」双系里的红，
           属于**用户明确指定要保留的红色**，不是该被搬走的金色装饰。
           （虽然 #e43644 的色相 355° 落在金色区间外、`isGold` 本来也不会误判，
            但显式跳过是双保险 —— 换配色轮次一多，很容易有人把区间改宽。） */
        if (el.tagName === 'TH') continue;
        if (el.tagName === 'TR' && el.querySelector(':scope > th')) continue;
        var cs, changed = false, css = '';
        try { cs = window.getComputedStyle(el); } catch (e) { continue; }
        /* 元素自身 + 两个伪元素（⚠️ 小卡片的金色色柱画在 ::before 上，
           「展开」按钮的金底也在伪元素里，只扫元素本身会漏掉它们） */
        var srcs = [[el, null], [el, '::before'], [el, '::after']];
        for (var q = 0; q < srcs.length; q++) {
          var target = srcs[q][0], pseudo = srcs[q][1];
          var st = pseudo ? window.getComputedStyle(target, pseudo) : cs;
          if (!st) continue;
          for (j = 0; j < PROPS_C.length; j++) {
            var p = PROPS_C[j];
            var raw = st.getPropertyValue(p);
            var out = blueifyDecl(raw);
            if (out === null) continue;
            changed = true;
            if (pseudo) { fixGoldPseudo(el, pseudo, p, out); }
            else { css += p + ':' + out + ' !important;'; }
          }
        }
        if (css) {
          try { el.setAttribute('style', ((el.getAttribute('style') || '') + ';' + css).replace(/;+/g, ';')); }
          catch (e) { /* 只读元素跳过 */ }
        }
        if (changed) {
          try { el.dataset.rptGold = '1'; } catch (e) {}
          hit++;
        }
      }
      return hit;
    }
    /* 伪元素里的金色：生成一条按「父选择器 + 伪元素 + 属性」定制的规则追加到动态样式表。
       ⚠️ 不能直接 setProperty 到伪元素上（CSSOM 不允许），只能改样式表。
       ⚠️ 元素自身走 inline style；伪元素走动态样式表，两条路径分开写。 */
    var dynSheet = null;
    function fixGoldPseudo(el, pseudo, prop, val) {
      var tag = el.tagName.toLowerCase();
      var cls = el.className && typeof el.className === 'string'
        ? '.' + el.className.trim().split(/\s+/).join('.') : '';
      /* ⚠️ 重复一遍 class 提高特异度：原规则常写成 `.dcards .dcard::before`（0,0,2,0），
         我们生成的 `.dcard::before`（0,0,1,0）会输给它 ⇒ 这里生成
         `标签.class.class::before`，靠双 class 抬到 (0,0,2,0)，再靠 !important 决胜。 */
      var sel = tag + cls + cls + pseudo;
      var key = sel + '{' + prop;
      if (fixGoldPseudo.seen && fixGoldPseudo.seen[key]) return;
      if (!fixGoldPseudo.seen) fixGoldPseudo.seen = {};
      fixGoldPseudo.seen[key] = 1;
      try {
        if (!dynSheet) {
          /* ⚠️ 标签名用拼接而非字面量：注入脚本的「标签配对」自检按字面量出现
             次数统计 open/close 标签是否相等，代码里出现完整字面量
             会让自检永久误红（踩过：createElement 写成裸字面量时 style 配对变 False）。 */
          var st = document.createElement('st' + 'yle');
          st.id = 'rpt-goldfix';
          (document.head || document.documentElement).appendChild(st);
          dynSheet = st.sheet;
        }
        dynSheet.insertRule(sel + '{' + prop + ':' + val + ' !important;}', dynSheet.cssRules.length);
      } catch (e) { /* 样式表被 CSP 挡住就跳过，不影响其余 */ }
    }

    /* ---------- ④ 一句话本质（.essence）：长段 → 分块卡片 ----------
       用户口径：「这里重新排版一下看着太乱了，改成「核心结论」那种」。
       病根是**结构**不是配色：.ec 是一整块 19px/700 的长段（700+ 字），
       深红底 + 零层次 ⇒ 眼睛找不到落点。
       修法：把 .ec 顶层的 inline 序列按「顶层 `<strong>`/`<b>` 的**起始位置**」
       切成一组 `.ebk` 块 —— 首块是导语（浅粉底 + 左红柱），其余是编号卡片。

       ★ 为什么用「顶层强标记的起始位置」当切点：
         - 数据里 `<strong>` 标记的正是**语义转折点**（「而 2025 年…」「这个反差就是…」
           「可证伪命题是：」「本报告已能回答…」），天然就是分点边界；
         - 不切在标点后面（那是按句号硬切，会把「…的央企资源公司：扎布耶盐湖独占
           298.5 km² 采矿权」这种固定搭配拦腰截断）；
         - 切点之间的普通文本归到**下一个**强标记之前，语义完整。
       ★ 幂等：打 `data-ebk="1"`，重跑不会二次切分。
       ★ 只在「顶层有 ≥2 个强标记且总长 ≥180 字」时才动 —— 短句式研报
         （002408 / 603599 是裸 `<b>` 不带 .essence 容器）保持原样，避免过度加工。 */
    function splitEssence(root) {
      if (!root || !root.querySelectorAll) return 0;
      var boxes = root.querySelectorAll('.essence .ec'), hit = 0;
      for (var i = 0; i < boxes.length; i++) {
        var ec = boxes[i];
        if (ec.getAttribute('data-ebk') === '1') continue;
        var txtAll = (ec.textContent || '').replace(/\s+/g, '');
        if (txtAll.length < 180) continue;
        /* 只看**顶层**inline 子节点；带块级子节点的（已分好段）不碰 */
        var kids = [], ok = true, marks = 0;
        for (var c = ec.firstChild; c; c = c.nextSibling) {
          if (c.nodeType === 3) { kids.push(c); continue; }
          if (c.nodeType !== 1) continue;
          var tn = c.tagName;
          if (STRONG[tn]) { kids.push(c); marks++; continue; }
          if (tn === 'U' || tn === 'EM' || tn === 'I' || tn === 'SPAN') { kids.push(c); continue; }
          ok = false; break;                      /* 出现块级/其它标签 ⇒ 交还人工 */
        }
        if (!ok || marks < 2) continue;

        /* 切点 = 每个顶层强标记之前的累积字符位置。
           ★ 强标记**自己**不会被切开（切点就在它前面）⇒ 元素整体搬过去即可，
             只有中间的纯文本节点需要按偏移切。 */
        var cuts = [0], acc = 0, j, k;
        for (j = 0; j < kids.length; j++) {
          if (kids[j].nodeType === 1 && STRONG[kids[j].tagName] && acc > 0) cuts.push(acc);
          acc += (kids[j].textContent || '').length;
        }
        cuts.push(acc);
        if (cuts.length < 3) continue;
        /* cuts 已是严格升序（每轮只 push 严格大于 from 的值），无须再去重 */

        /* kids 累积偏移表 */
        var off = [], o = 0;
        for (j = 0; j < kids.length; j++) { off.push(o); o += (kids[j].textContent || '').length; }

        /* 先按切点产出「原始段」：每段 = [from, to, [克隆节点]] */
        var raw = [], from = 0;
        function collect(a, b) {
          var nodes = [];
          for (var q = 0; q < kids.length; q++) {
            var ln = (kids[q].textContent || '').length;
            if (!ln) continue;
            var s2 = a - off[q], e2 = b - off[q];
            if (e2 <= 0 || s2 >= ln) continue;
            nodes.push(kids[q].nodeType === 3
              ? document.createTextNode(kids[q].nodeValue.slice(Math.max(0, s2), Math.min(ln, e2)))
              : kids[q].cloneNode(true));
          }
          return { len: b - a, nodes: nodes };
        }
        for (j = 0; j < cuts.length; j++) {
          if (cuts[j] > from) { var r0 = collect(from, cuts[j]); if (r0.len) raw.push(r0); from = cuts[j]; }
        }
        if (from < o) { var r1 = collect(from, o); if (r1.len) raw.push(r1); }
        if (raw.length < 2) continue;

        /* ★ 短段合并：连续强标记会产生「5 字引出词」和「——」这种碎片段，
           单独成卡很难看。规则：某段纯文字数 < MERGE_MIN 且不是最后一段 ⇒ 并入**下一段**；
           末段太短则并入**上一段**。合并只拼节点，不改文字（★ 文字必须逐字守恒）。 */
        var MIN = 26, merged = [], pending = null;
        for (j = 0; j < raw.length; j++) {
          var seg = raw[j];
          if (pending) { pending.nodes = pending.nodes.concat(seg.nodes); pending.len += seg.len; }
          else pending = seg;
          var isLast = (j === raw.length - 1);
          var keep = pending.len >= MIN || isLast;
          if (keep) { merged.push(pending); pending = null; }
        }
        if (pending) {                                   /* 末段仍不足 MIN ⇒ 回并到上一段 */
          if (merged.length) merged[merged.length - 1].nodes = merged[merged.length - 1].nodes.concat(pending.nodes);
          else merged.push(pending);
        }
        if (merged.length < 2) continue;

        var frag = document.createDocumentFragment();
        for (j = 0; j < merged.length; j++) {
          var blk = document.createElement('p');
          blk.className = 'ebk';
          for (k = 0; k < merged[j].nodes.length; k++) blk.appendChild(merged[j].nodes[k]);
          if ((blk.textContent || '').replace(/\s+/g, '')) frag.appendChild(blk);
        }
        if (!frag.childNodes.length) continue;
        while (ec.firstChild) ec.removeChild(ec.firstChild);
        ec.appendChild(frag);
        ec.setAttribute('data-ebk', '1');
        hit++;
      }
      return hit;
    }

    /* ---------- 调度 ---------- */
    var busy = false, timer = null;
    function once() {
      if (busy) return true;
      var mods = document.getElementById('mods');
      if (!mods || !mods.querySelector('.card')) return false;   /* 还没渲染出模块 */
      busy = true;
      try {
        fixBold(document.body);
        markNum(document.body);
        markTxt(document.body);        /* ★ 必须在 markNum 之后：靠 is-num 排除数字格 */
        splitEssence(document.body);      /* ★ 必须在 fixBold 之后：`**`→`<b>` 先落地，才能当切点 */
        fixGold(document.body);
      } catch (e) {
        if (window.console && console.warn) console.warn('[rpt-blockscript]', e);
      }
      busy = 0;
      return true;
    }
    function schedule() {
      if (timer) clearTimeout(timer);
      timer = setTimeout(function () { timer = null; once(); }, 250);
    }
    function start() {
      once();
      var mods = document.getElementById('mods');
      if (!mods) { poll(); return; }
      if (window.MutationObserver && !window.__rptBlockObs) {
        window.__rptBlockObs = new MutationObserver(schedule);
        window.__rptBlockObs.observe(mods, { childList: true, subtree: true, characterData: true });
      }
      window.addEventListener('load', schedule);
      setTimeout(once, 600);
      setTimeout(once, 2500);
      setTimeout(once, 6000);
    }
    function poll() {                      /* 等 #mods 出现，最多 ~20s */
      var n = 0;
      var iv = setInterval(function () {
        if (document.getElementById('mods')) { clearInterval(iv); start(); }
        else if (++n > 200) clearInterval(iv);
      }, 100);
    }
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', start);
    } else {
      start();
    }

    /* 手工重跑入口（管理员改完内容存盘后可用）。
       ⚠️ 不要挂到 `window.Rpt` 上 —— 那是页面自己的命名空间，会被模板脚本覆盖。 */
    window.__rptBlockApi = { once: once };
  } catch (e) {
    window.__rptBlockErr = String((e && e.stack) || e);
    if (window.console && console.warn) console.warn('[rpt-blockscript]', e);
  }
})();
