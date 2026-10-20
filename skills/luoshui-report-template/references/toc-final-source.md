# 左侧竖排目录 · 最终版源码（逐字照抄）

> **本文件是「抄作业」用的**：要改/重建目录，先看 `frontend-style.md` §1.6 的规范与坑，
> 再回来整段复制这里的代码。**下面三段是从线上 `report.html` 里原样抓出来的**，不是手写复述。
>
> 线上快照：md5 **`7c92809c`** · 3,926,243 字节 · 2026-10-20（第八次微调：序号 15px / 标题 13px）
> 抓取方式：`curl` 线上 → 按「`nav.toc{` 前一个 `/*`」到「`核心结论（2026-10-14 版式重做）` 前一个 `/*`」
> 截 CSS 段；`renderToc()` / `tocSpy()` 各整函数截取。⚠️ 段落边界别用中文标题去定位（`.wrap` 注释里也有同样四个字）。

## 0. 落地位置与三步替换

| 段 | 源文件 | 位置 | 落点 |
|---|---|---|---|
| ① CSS 段 | `build/report_theme.css` | `nav.toc` 起，直到「核心结论」模块注释之前 | `report.html` 的 `<style>` 区 |
| ② 壳 | `deploy/report.template.html` | `function renderToc()` | 同文件 JS 区 |
| ③ 滚动联动 | `deploy/report.template.html` | `function tocSpy()` | 同文件 JS 区 |

⚠️ 上线**不要**整页重新 build 后全量覆盖（本地 `block_style.css` 等常有未发布改动）——
一律 `curl` 拉线上 → 只替换这三段 → 断言其余字节逐字节相同 → `tcb hosting deploy`。

## 1. CSS 段（`build/report_theme.css`，含 1427 / 1360 / 760 三档断点）

```css
/* ============================================================
     左侧竖排目录 —— 2026-10-20 第四版「参考稿 · 精致重读」
     ------------------------------------------------------------------
     ★ 用户给了参考稿（暖白卡 / ●目录 + 03/10 计数 / 两位数序号 /
       深墨大圆角选中 + 右侧金点 / 底部阅读进度条 / 回到顶部按钮），
       要求「按这个样式改的花里胡哨一点」。
     ★ 前三版别复活：亮红实色（塑料）→ 墨玉金箔（老气）→ 纯白玻璃（太素）。
       本版＝白玻璃的骨 + 参考稿的壳：所有「花」都花在**信息与小结构**上，
       不用大面积渐变，避免又滑回前两版的坑。
     ★ 壳由 renderToc() 生成（`.tc-hd` / `.tc-ft`），计数与进度由 tocSpy()
       随滚动刷新 —— **不新增任何库字段**，纯渲染层。
     ⚠️ 宽度 136 是硬上限：1440 视口下目录右缘 168 vs 正文左缘 192，余量 24px。
     ⚠️ `backdrop-filter` 只准用这一块（整页 3.9 MB，多加会拖滚动）。
     ≥1361px 完整竖排；≤1360px 序号胶囊（悬停展开成全卡）；≤760px 底部横排条
     ============================================================ */
  nav.toc{
    position:fixed;z-index:80;
    /* ★ 164 宽：left 反推自「目录右缘 = 正文左缘 − 10px」。
       正文 `.wrap` 1100 + padding 20 ⇒ 内容左缘 = 50% − 530；目录右缘 = 50% − 540
       ⇒ left = 50% − 540 − 164 = calc(50% − 704px)。1440 视口下落在 16px。
       ⚠️ 需要 ≥1428px 才放得下，以下回退到 136（见 1427 断点）。 */
    left:max(10px,calc(50% - 704px));top:50%;transform:translateY(-50%);
    width:178px;max-height:88vh;overflow-y:auto;overscroll-behavior:contain;
    /* ★ 方角（2026-10-20 用户令「四个角改成方的」）：20px → 0。
       条目与「回到顶部」按钮一起走方角，整卡才像一张表格纸而不是贴纸。 */
    display:flex;flex-direction:column;gap:0;
    padding:14px 10px 12px;border-radius:0;
    /* 底色 + 右下角一点极淡金晕（参考稿的暖光收尾，透明度只 9%，不是大面积渐变） */
    background:
      radial-gradient(120% 78% at 108% 106%,rgba(201,162,39,.09) 0%,rgba(201,162,39,0) 62%),
      rgba(255,253,248,.92);
    -webkit-backdrop-filter:blur(22px) saturate(160%);
    backdrop-filter:blur(22px) saturate(160%);
    border:1px solid rgba(20,16,14,.06);
    box-shadow:
      0 1px 2px rgba(20,16,14,.04),
      0 18px 44px -14px rgba(20,16,14,.22),
      inset 0 1px 0 rgba(255,255,255,.9);
    scrollbar-width:none;
    transition:box-shadow .28s ease,border-color .28s ease;
  }
  nav.toc::-webkit-scrollbar{display:none;}
  /* 序号列的竖线已**整体移除**（2026-10-20 用户令「竖线不要了」）。
     前六版走过的坑记在这里，别再花时间重试：4/9px 小段＝一串横点、
     24px 段＝一列断横、段长 = 周期−5px 才连续；`mask-image` 是唯一能做出
     「整条线红→金」的写法（`repeating-linear-gradient` 画色会让每段各自重来一遍）。
     现在改由「每行标题下的下划线」分隔条目 —— 见 `nav.toc a` 的第一层背景。 */
  nav.toc:hover{
    border-color:rgba(20,16,14,.13);
    box-shadow:
      0 1px 2px rgba(20,16,14,.04),
      0 24px 52px -16px rgba(20,16,14,.28),
      inset 0 1px 0 rgba(255,255,255,.94);
  }
  /* ---------- 顶栏：● 目录 …………… 03 / 10 ---------- */
  .tc-hd{
    display:flex;align-items:center;gap:6px;flex:0 0 auto;
    padding:2px 6px 11px;margin-bottom:5px;
    border-bottom:1px solid rgba(20,16,14,.06);
  }
  .tc-dt{
    width:7px;height:7px;border-radius:50%;flex:0 0 auto;background:#c9a227;
    box-shadow:0 0 0 3px rgba(201,162,39,.15);
  }
  .tc-tt{
    flex:1 1 auto;font-size:11px;font-weight:700;letter-spacing:.16em;
    text-indent:.16em;color:#948a7c;
  }
  .tc-ix{
    flex:0 0 auto;font-size:10px;font-weight:600;letter-spacing:.05em;
    color:rgba(20,16,14,.30);font-variant-numeric:tabular-nums;
  }
  .tc-ix b{color:#b08a1f;font-weight:800;}
  .tc-ix em{font-style:normal;opacity:.55;margin:0 2px;}
  /* ---------- 条目：01 │ 模块名 ---------- */
  nav.toc a{
    position:relative;display:block;flex:0 0 auto;
    font-size:13px;font-weight:500;line-height:1.4;
    /* ★ 文字居中（2026-10-20 用户令）：左右 padding 对称，序号仍是绝对定位在左侧，
       所以「01 … 模块名 … ●」是居中排版里的一条左侧索引，不再占正文缩进。 */
    padding:10px 12px;text-align:center;border-radius:0;
    color:#5a5148;text-decoration:none;
    white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
    /* ★ 两层背景（2026-10-20 用户令「每条目录标题下加一个下划线」）：
       ① 下划线：**左右各留 12px 对称**（`size:calc(100% - 24px) 2px`，不是从文字起点量）、
          高 **2px**、**红金渐变**（朱砂 80% → 赭红 62% → 金 52% → 淡金 16%），
          向右渐隐收尾，所以它像「标题的下划线」而不是通栏分割线；
       ② hover 金带：从左往右展开（0% → 100%），换底色是硬跳变、没有动感。
       ★ 两层必须写成两条 background-size（逗号分隔），hover 时只改第二层宽度，
         第一层保持 `calc(100% - 24px) 2px`，否则下划线会跟着撑成整块灰底。 */
    background-image:
      linear-gradient(90deg,rgba(192,57,43,.80) 0%,rgba(163,34,30,.62) 34%,rgba(193,145,31,.52) 72%,rgba(232,200,92,.16) 100%),
      linear-gradient(90deg,rgba(201,162,39,.17) 0%,rgba(201,162,39,.06) 58%,rgba(201,162,39,0) 100%);
    background-repeat:no-repeat,no-repeat;
    /* 下划线：加粗到 **2px**、左右各留 12px 对称（文字居中后，若还按「文字起点 34px」偏移会一边长一边短） */
    /* ★ 上移 **8px** 贴着自己的文字：贴到行底会与下一行（选中时是深墨块）顶边贴死，
       看起来像被压掉一截（2026-10-20 用户截图）。 */
    background-position:50% calc(100% - 8px),left center;
    background-size:calc(100% - 24px) 2px,0% 100%;
    transition:background-size .4s cubic-bezier(.22,.8,.36,1),
               color .22s ease,
               transform .3s cubic-bezier(.22,.8,.36,1),
               box-shadow .3s ease;
  }
  /* 最后一条不画线（下面紧接「阅读进度」区，已有分隔线，再画一条会成双线） */
  nav.toc a:last-of-type{background-image:none;}
  /* 两位数序号：读 `data-n`（补零串），不是 `data-i`（纯数字，探针在用） */
  nav.toc a::before{
    content:attr(data-n);
    position:absolute;left:11px;top:50%;transform:translateY(-50%);
    font-size:15px;font-weight:700;letter-spacing:.01em;
    font-variant-numeric:tabular-nums;color:rgba(20,16,14,.26);
    transition:color .22s ease,transform .3s cubic-bezier(.22,.8,.36,1);
  }
  nav.toc a:hover{
    background-size:calc(100% - 24px) 2px,100% 100%;
    color:#14100e;
    /* ★ 不再右移 3px（2026-10-20 方角改版）：条目不缩进、通栏铺满，
       一移位文字就不在同一列上，列表的「对齐感」反而没了。 */
    box-shadow:inset 3px 0 0 -1px rgba(201,162,39,.55),0 3px 12px -6px rgba(20,16,14,.24);
  }
  nav.toc a:hover::before{color:#b08a1f;transform:translateY(-50%) scale(1.12);}
  /* 选中：深墨块 + 金序号 + 右侧金点（方角，与卡片四角一致） */
  nav.toc a.on{
    background:linear-gradient(180deg,#241d19 0%,#15100e 100%);
    background-size:100% 100%;
    color:#fbf8f2;font-weight:600;
    box-shadow:0 6px 16px -8px rgba(20,16,14,.55);
    transition:background .3s ease,color .2s ease,box-shadow .3s ease,transform .3s cubic-bezier(.22,.8,.36,1);
  }
  nav.toc a.on::before{color:#d8b64a;}
  nav.toc a.on::after{
    content:'';position:absolute;right:10px;top:50%;transform:translateY(-50%);
    width:5px;height:5px;border-radius:50%;background:#d8b64a;
    box-shadow:0 0 0 3px rgba(201,162,39,.16);
  }
  /* ---------- 底栏：阅读进度 + 回到顶部 ---------- */
  .tc-ft{
    display:block;flex:0 0 auto;margin-top:6px;padding:11px 5px 2px;
    border-top:1px solid rgba(20,16,14,.06);
  }
  .tc-pg{
    display:flex;align-items:baseline;justify-content:space-between;
    font-size:9px;letter-spacing:.03em;color:#a29786;
  }
  .tc-pg b{color:#b08a1f;font-weight:800;font-size:10.5px;font-variant-numeric:tabular-nums;}
  .tc-bar{
    height:3px;border-radius:2px;background:rgba(20,16,14,.07);
    margin:7px 0 11px;overflow:hidden;
  }
  .tc-bar i{
    display:block;height:100%;width:0;border-radius:2px;
    background:linear-gradient(90deg,#e0c268,#c9a227);
    transition:width .3s ease;
  }
  .tc-up{
    display:block;width:100%;padding:8px 0;margin:0;
    font:inherit;font-size:11px;font-weight:600;letter-spacing:.06em;
    color:#7a7168;background:transparent;cursor:pointer;
    border:1px solid rgba(20,16,14,.10);border-radius:0;
    transition:background .16s ease,color .16s ease,border-color .16s ease;
  }
  .tc-up::before{content:'\2191\00a0';font-weight:700;color:#b08a1f;}
  .tc-up:hover{background:rgba(20,16,14,.045);color:#14100e;border-color:rgba(20,16,14,.18);}
  /* 锚点定位补偿：点目录跳过去时，模块标题不被顶部操作条压住。
     ⚠️ 2026-09-20：目录新增「投资核心」锚到页面顶部的核心结论区（#verdict，
     不是模块卡），所以要一并给 #verdict 补 scroll-margin-top，
     否则点目录跳过去时核心结论会被固定顶栏压掉一截。 */
  .card[id], #verdict{scroll-margin-top:86px;}
  /* 1361~1427px：正文两侧只剩 ~140px，164 会压住正文 ⇒ 回退到 136（尺寸跳一档，但没有重叠） */
  @media(max-width:1427px){
    nav.toc{left:max(10px,calc(50% - 656px));width:136px;padding:11px 8px 9px;border-radius:0;max-height:86vh;}
    .tc-hd{gap:5px;padding:1px 5px 9px;margin-bottom:4px;}
    .tc-dt{width:6px;height:6px;}
    .tc-tt{font-size:10px;letter-spacing:.14em;text-indent:.14em;}
    .tc-ix{font-size:9px;}
    nav.toc a{font-size:12px;padding:7px 8px;border-radius:0;text-align:center;
      background-size:calc(100% - 16px) 2px,0% 100%;background-position:50% calc(100% - 6px),left center;}
    nav.toc a:hover{background-size:calc(100% - 16px) 2px,100% 100%;}
    nav.toc a::before{left:8px;font-size:13px;}
    nav.toc a.on{padding-right:8px;}
    nav.toc a.on::after{right:9px;width:4px;height:4px;}
    .tc-ft{padding:9px 4px 1px;margin-top:5px;}
    .tc-pg{font-size:8.5px;}
    .tc-pg b{font-size:9.5px;}
    .tc-bar{height:2px;margin:6px 0 9px;}
    .tc-up{padding:6px 0;font-size:10px;}
  }
  /* 窄屏：目录收成「序号胶囊」，悬停 / 聚焦后展开成全卡 */
  @media(max-width:1360px){
    body{padding-left:62px;}
    nav.toc{left:9px;width:46px;padding:9px 6px 10px;border-radius:0;max-height:86vh;}
    .tc-hd,.tc-ft{display:none;}
    /* 胶囊态只有序号，下划线会变成一串短横 ⇒ 收起时不画，展开回全卡再恢复 */
    nav.toc a{font-size:0;padding:10px 0;text-align:center;background-image:none;}
    /* ★ text-align 必须显式回收：宽屏给它的是继承值，static 后会让序号贴右沿 */
    nav.toc a::before{
      position:static;transform:none;display:block;width:auto;
      margin:0;font-size:10px;font-weight:700;text-align:center;
    }
    nav.toc a.on{padding-right:0;}
    nav.toc a.on::after{content:none;}
    nav.toc:hover,nav.toc:focus-within{width:178px;padding:14px 10px 12px;border-radius:0;}
    nav.toc:hover .tc-hd,nav.toc:focus-within .tc-hd{display:flex;padding:2px 6px 11px;margin-bottom:5px;gap:6px;}
    nav.toc:hover .tc-tt,nav.toc:focus-within .tc-tt{font-size:11px;letter-spacing:.16em;text-indent:.16em;}
    nav.toc:hover .tc-ix,nav.toc:focus-within .tc-ix{font-size:10px;}
    nav.toc:hover .tc-ft,nav.toc:focus-within .tc-ft{display:block;padding:11px 5px 2px;margin-top:6px;}
    nav.toc:hover .tc-pg,nav.toc:focus-within .tc-pg{font-size:9px;}
    nav.toc:hover .tc-pg b,nav.toc:focus-within .tc-pg b{font-size:10.5px;}
    nav.toc:hover .tc-bar,nav.toc:focus-within .tc-bar{height:3px;margin:7px 0 11px;}
    nav.toc:hover .tc-up,nav.toc:focus-within .tc-up{padding:8px 0;font-size:11px;}
    nav.toc:hover a,nav.toc:focus-within a{font-size:13px;padding:10px 12px;text-align:center;
      background-image:
        linear-gradient(90deg,rgba(192,57,43,.80) 0%,rgba(163,34,30,.62) 34%,rgba(193,145,31,.52) 72%,rgba(232,200,92,.16) 100%),
        linear-gradient(90deg,rgba(201,162,39,.17) 0%,rgba(201,162,39,.06) 58%,rgba(201,162,39,0) 100%);
      background-repeat:no-repeat,no-repeat;background-position:50% calc(100% - 8px),left center;
      background-size:calc(100% - 24px) 2px,0% 100%;}
    /* ★ 展开回全卡时序号必须回到主档的 15px：胶囊里是 10px 的小前缀，
       但展开后若仍是 10px，就比 13px 的标题还小 —— 字号层次整个反过来（2026-10-20 修）。 */
    nav.toc:hover a::before,nav.toc:focus-within a::before{
      position:absolute;left:11px;top:50%;transform:translateY(-50%);
      width:auto;margin:0;font-size:15px;text-align:left;
    }
    nav.toc:hover a.on,nav.toc:focus-within a.on{padding-right:12px;}
    nav.toc:hover a.on::after,nav.toc:focus-within a.on::after{content:'';width:5px;height:5px;right:10px;}
  }
  /* 手机：目录改成底部横排条，横向可滑 */
  @media(max-width:760px){
    body{padding-left:0;padding-bottom:72px;}
    nav.toc{
      left:0;right:0;bottom:0;top:auto;transform:none;width:auto;max-height:none;
      flex-direction:row;gap:4px;overflow-x:auto;overflow-y:hidden;
      padding:8px 10px;border-radius:0;
      border-width:1px 0 0;border-color:rgba(20,16,14,.10);
      background:rgba(255,253,248,.95);
      box-shadow:0 -10px 28px -8px rgba(20,16,14,.18),inset 0 1px 0 rgba(255,255,255,.9);
    }
    .tc-hd,.tc-ft{display:none !important;}
    nav.toc a,nav.toc:hover a{
      flex:0 0 auto;font-size:12.5px;padding:7px 12px 7px 25px;text-align:left;
    }
    nav.toc a::before,nav.toc:hover a::before{
      position:absolute;left:9px;top:50%;transform:translateY(-50%);
      width:auto;margin:0;font-size:8.5px;text-align:left;
    }
    nav.toc a:hover{transform:none;}
  }
```

## 2. 壳：`renderToc()`（`deploy/report.template.html`）

```javascript
function renderToc(){
  var t = (St.rep && St.rep.toc) || [];
  var box = $('toc');
  if(!t.length){ box.innerHTML = ''; box.style.display = 'none'; return; }
  var links = t.map(function(x, i){
    /* ★ 条目**不加 title**（2026-10-20 用户令：「那个悬浮的投资核心不要」）：
       浏览器原生提示条会在 hover 时弹出一条黑底「投资核心」横在列表上，
       比条目本身还显眼。截断靠 CSS 的 ellipsis，不要用 title 兜。 */
    return '<a href="#' + attr(x.anchor) + '" data-i="' + (i + 1) + '" data-n="' + tocPad2(i + 1) + '">' +
           esc(tocLabel(x.text)) + '</a>';
  }).join('');
  /* 目录壳（2026-10-20 用户给了参考稿，要「花里胡哨」）：
     顶部「● 目录 03/10」+ 条目 + 底部「阅读进度条 + 回到顶部」。
     ★ 三块壳全由渲染层生成，**不加任何库字段**；计数与进度在 tocSpy() 里跟着滚动刷新。 */
  box.innerHTML =
    '<div class="tc-hd"><i class="tc-dt"></i><span class="tc-tt">目录</span>' +
      '<span class="tc-ix"><b>01</b><em>/</em>' + tocPad2(t.length) + '</span></div>' +
    links +
    '<div class="tc-ft">' +
      '<div class="tc-pg"><span>阅读进度</span><b>0%</b></div>' +
      '<div class="tc-bar"><i></i></div>' +
      '<button type="button" class="tc-up" onclick="try{window.scrollTo({top:0,behavior:\'smooth\'});}catch(e){window.scrollTo(0,0);}return false;">回到顶部</button>' +
    '</div>';
  box.style.display = '';
  /* ★ 序号列那条竖线已下线（2026-10-20 用户令「竖线不要了」），
     `--tc-lt/--tc-lh/--tc-step` 三个几何变量随之删除；条目分隔改由每行的下划线承担。 */
  tocSpy();
}

/* 左侧竖排目录：滚动时高亮当前模块（顶部操作条会压住定位点，预留 110px 余量） */
function tocSpy(){
  var box = $('toc');
  if(!box) return;
  var as = box.querySelectorAll('a');
  if(!as.length) return;
  var cur = 0;
  for(var i = 0; i < as.length; i++){
    var id = String(as[i].getAttribute('href') || '').replace(/^#/, '');
    var el = id ? document.getElementById(id) : null;
    if(!el) continue;
    var rc = el.getBoundingClientRect();
    /* ⚠️ display:none 的模块 rect 全是 0，会被误判成「已经在视口上方」→ 必须跳过 */
    if(!rc.height) continue;
    if(rc.top <= 110) cur = i;
  }
```

## 3. 滚动联动：`tocSpy()`（同文件，零写库，只改 DOM）

```javascript
function tocSpy(){
  var box = $('toc');
  if(!box) return;
  var as = box.querySelectorAll('a');
  if(!as.length) return;
  var cur = 0;
  for(var i = 0; i < as.length; i++){
    var id = String(as[i].getAttribute('href') || '').replace(/^#/, '');
    var el = id ? document.getElementById(id) : null;
    if(!el) continue;
    var rc = el.getBoundingClientRect();
    /* ⚠️ display:none 的模块 rect 全是 0，会被误判成「已经在视口上方」→ 必须跳过 */
    if(!rc.height) continue;
    if(rc.top <= 110) cur = i;
  }
```

## 4. 三档断点速查

| 视口 | 目录形态 | 标题 | 序号 | 下划线 |
|---|---|---|---|---|
| ≥1428px | 竖排全卡 **178** 宽 | 13px / 行高 1.4 | **15px** / 700 | `calc(100% - 24px) 2px` @ `50% calc(100% - 8px)` |
| 1361~1427px | 竖排全卡 **136** 宽 | 12px | **13px** | `calc(100% - 16px) 2px` @ `50% calc(100% - 6px)` |
| ≤1360px | **46 宽序号胶囊**，hover 展开回 178 | 收起 0 / 展开 13px | 收起 10px / **展开 15px** | 收起 `none` / 展开同主档 |
| ≤760px | 底部横排条（横向可滑） | 12.5px | 8.5px（小前缀） | 无 |

★ 三处（主档 / 1427 / 胶囊展开）**字号必须一起改**，少一处展开时会闪回旧字号。
★ 胶囊展开态的序号若留在 10px，会比 13px 的标题还小 —— **层次反转**（2026-10-20 修过一次）。

## 5. 验收链（全绿才算改完）

```bash
python build/_toc5_mk.py                    # 生成 _work/p5.html + 严格超集自检
python build/_toc5_probe.py _work/p5.html   # 34 项：方角/双层背景/无竖线/字号层次/三档/tocSpy/43 表溢出
python build/_toc5_shot.py                  # 1440 特写 / hover 模拟 / 1200 胶囊 / 390 横排
```

部署后必做：`curl` 回读 md5 与本地逐字节比对 → 对回读文件再跑一次 `_toc5_probe.py` → `probe_blockstyle.py <code>`。

## 6. 不要复活的东西

- **竖线**（`::before` 已删、`--tc-lt/--tc-lh/--tc-step` 已撤）：4/9px 小段＝一串横点、24px 段＝一列断横。
- 条目上的 `title`（hover 会弹浏览器原生黑底提示条）。
- 七版被否的配色与壳形：亮红实色 / 墨玉金箔 / 纯白玻璃 / 小号参考稿壳 / 4px 虚线点 / 连续竖线。
- `nav.toc a.on` 里写 `background` 简写后**忘了补 `background-size:100% 100%`**（会把 hover 光带撑歪）。
