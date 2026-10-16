# -*- coding: utf-8 -*-
"""m11「收入 / 毛利结构」全站统一为**左右分开的两个环**（2026-10-14 用户口径）。

用户原话：
  「宝钛股份这个右边也改成左边一样的图形样式，别的研报也都使用这个样式」（第一轮）
  「所有的这个图做成分开的两个图，负数不显示，在下边写个注释」（第二轮 ⇒ 本版）

本版三件事：
  1. **分开的两个图**：原来是「外环＝收入、内环＝毛利」的同心双环，现改为
     **左环＝收入构成、右环＝毛利构成**，两环同半径、各自带扇区标签与引线，
     环下各有一枚小标题（`title` 数组按百分比居中）。
  2. **负数不显示**：环上画不出负弧长 —— 上一版是「取绝对值 + 斜纹 + 真值进 tooltip」，
     用户要求直接不显示 ⇒ `drop_neg()` 把带负值标记的扇区整条剔除，真值写进图下注释。
  3. **图下注释**：`data-ringnote` 段落同步改写为「左图＝…，右图＝…」。

────────────────────────────────────────────────────────────────────────
为什么是「两个 pie series 各给一个 center」而不是 ECharts 的嵌套 `children`：
  2026-10-14 用最小页面 + SVG 渲染器实测本仓库的 echarts 5.5.1 构建：
    · 单 series 嵌套 children  → ✗ 只画出 3 个扇区、内环不出现、itemStyle.color 被忽略
    · 两个 pie series 相邻半径 → ✓ 6 个扇区
    · graphic 组件             → ✓ 可用（本脚本最终未使用，理由见下）
    · itemStyle.decal 斜纹     → ✓ 可用（本版起不再使用）

────────────────────────────────────────────────────────────────────────
三个必须遵守的渲染层事实（否则写进库也显示不对）：
  1. **配色一律写在 `series[i].color` 数组里，不要写 data 项的 `itemStyle.color`。**
     report.template.html 的 beauty() 会把根级 `opt.color` 与**饼图 data 项的
     itemStyle.color** 逐个过 `btRetint()` 做色族归一（红族按明度塌成 4 档、
     暖灰粉去粉）；而 `series[i].color` 它一个字都不碰。
     实测 `#c8102e` 会被 retint 成 `#d0202f`、`#dcb9be` 会被刷成亮红 `#dd3543` ——
     全站已有的 000731 / 000830 环形图正是把 7 色数组放在 series.color 才保住了原色。
  2. **tooltip 用 `{{fn:ringTip}}` 令牌**（revive() 只在「整串匹配」时才还原成函数）。
     ECharts 的 `{d}` 是归一化后的百分比、不是报告口径真值，所以真值随数据点存进
     `data[i].tip`，由 ringTip 原样吐出。
  3. **不用 graphic 放环下小标题**：graphic 只能按 px/百分比定位，`left:'26%'` 配
     `style.textAlign:'center'` 的居中语义在各版本间不一致；改用 `title` 数组 ——
     `left` 给百分比 + `textAlign:'center'` 是 ECharts 官方支持的「以百分比为居中点」写法。
     环的含义由**环下小标题 + 图下一行口径说明**共同承担。

────────────────────────────────────────────────────────────────────────
数据口径（★ 关键：**不编造数字**）：
  · 左环＝收入占比，直接取自该报告 m11 表格的「收入占比」列。
  · 右环＝毛利贡献占比。**当且仅当**该报告逐项披露了毛利率才画右环：
      - 600456 直接用 m11 表里已披露的「毛利占比」列（含一个负值 ⇒ 本轮起不显示）；
      - 600392 用 m11 表里已披露的「毛利贡献（亿元）」列；
      - 000830 / 601958 / 002408 / 603599 / 603977 由「收入占比 × 毛利率」
        逐项推算后归一化 —— 推算口径写在图下说明里，不冒充实测值；
      - 601958 的推算结果与年报披露的「钼炉料毛利占比 63.22%」吻合（脚本会断言）；
      - 601118 分项毛利率整列未披露 ⇒ 只画单环（居中），并在说明里写明原因；
      - 603977 仅两个板块披露毛利率（覆盖 73.0% 收入）⇒ 右环只含这两项，覆盖度写进说明。
  · **负值**：环上不显示（`drop_neg()` 整条剔除），真值与被剔除的事实写进图下注释，
    绝不改成 0 也不悄悄翻正。

────────────────────────────────────────────────────────────────────────
幂等：写库前先读回、比对本脚本生成的规范 JSON，相同则跳过（打印「已是目标形态」）。
      模块 HTML 里的说明段落带 `data-ringnote="1"`，重跑时**替换**而不是追加。

用法：
  python3 mkmod11_ring.py --dry     # 只打印将要写入的 opt 与说明，不碰库
  python3 mkmod11_ring.py           # 写库（图表 opt + 图下说明）
  python3 mkmod11_ring.py --check   # 只读校验：库里的内容是否与 SPEC 一致
  python3 mkmod11_ring.py --emit /tmp/ring_payload.json   # 导出给预览探针
  python3 mkmod11_ring.py --only 603227   # ★ 只处理指定标的（逗号分隔多个），
                                          #   新增研报时用，避免顺手动到其他 8 份
"""
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
HERE = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(io.open(os.path.join(HERE, 'cloud.json'), encoding='utf-8'))
REST = 'https://%s.api.tcloudbasegateway.com/v1/rdb/rest/' % CFG['envId']
HDR = {'Authorization': 'Bearer ' + CFG['key'], 'Content-Type': 'application/json',
       'Prefer': 'return=minimal'}

# 全站既有环形图（000731 / 000830）的 7 色数组，放在 series.color 里不受 beauty 重映射
PAL = ['#c8102e', '#c9a227', '#e8939c', '#8c0a20', '#dcb9be', '#a5762a', '#caa2a8']
NEG = '#0b8a5c'                      # 负值色（本轮起不再用于弧长，仅保留常量）
# ── 并排双环（2026-10-14 用户令：「做成分开的两个图」）────────────────────
# 原来是外环/内环**同心**；现改为**左右两个独立的环**：左＝收入构成、右＝毛利构成。
# 两环同半径、各自带扇区标签与引线，环下各有一枚小标题（title 数组，按百分比居中）。
RAD = ['40%', '62%']                 # 并排时两个环共用这一对半径
CEN_L = ['26%', '50%']               # 左环（收入构成）圆心
CEN_R = ['74%', '50%']               # 右环（毛利构成）圆心
CAP_L, CAP_R = '收入构成', '毛利构成'  # 环下小标题文案
CAP_BOTTOM = 26                      # 小标题距画布底 px（给 legend 让位）
RAD_ONE = ['50%', '70%']             # 单环（601118 分项毛利率未披露）保持居中
CEN_ONE = ['50%', '46%']
# ★ 标签必须写成**两行**（名字 / 百分比）：
#   600456 首版用单行 `{b} {d}%`，466px 宽的并排槽位里「其他金属产品 7.85%」与
#   「其他业务 6.17%」两个相邻小扇区的标签在左上角糊成一团（实测截图）。
#   两行把标签宽度砍掉约一半，引线也更容易分开。
# ★ 百分比用 `{c}` 而**不是** `{d}`：`{d}` 是 ECharts 归一化后的占比，分母是各扇区之和。
#   601958 五项收入占比加总是 99.99% ⇒ `{d}` 打出「65.43%」，而同一张表上写的是 65.42%
#   —— 图与表差一个数字，读者会当成数据错误。`{c}` 直接取我们写进 data 的原值，
#   最多只是「3.2% vs 3.20%」这种尾零差异，不会出现错位数字。
LBL_FMT = '{b}\n{c}%'

# ─────────────────────────── 规格表 ───────────────────────────
# code → {chart, name, title_old/title_new(可选，改 h3), outer, inner, note}
#   outer / inner: [(显示名, 数值, tooltip 文案)]；数值即扇区弧长依据（内环取绝对值）
SPEC = {
    '600456': {
        'chart': 'chartGrossMix',
        'name': '收入与毛利构成（2025·左右双环）',
        'retitle': ('<h3>毛利构成（2025）</h3>', '<h3>收入与毛利构成（2025）</h3>'),
        'outer': [('钛产品', 85.99, '85.99%'),
                  ('其他金属产品', 7.85, '7.85%'),
                  ('其他业务', 6.17, '6.17%')],
        'inner': [('钛产品', 102.00, '102.00%'),
                  ('其他金属产品', 2.12, '−2.12%（毛利为负，按规定不在环上显示）', True),
                  ('其他业务', 0.07, '0.07%')],
        'note': '左图＝收入构成，右图＝毛利构成（均为 2025 年报分产品口径）。'
                '⚠️ 其他金属产品毛利为负（毛利率 −5.36%、毛利占比 −2.12%），<b>不在右图中显示</b>；'
                '因此右图接近单色 —— 这恰好说明毛利几乎全部来自钛产品。'
                '右图钛产品标注 102.00% 高于 100%，系该板块亏损摊薄合并毛利所致（上表同口径）。',
    },
    '000830': {
        'chart': 'chartMix',
        'name': '收入与毛利构成（2026H1·左右双环）',
        'outer': [('化工新材料', 66.69, '66.69%'),
                  ('基础化工', 17.25, '17.25%'),
                  ('化肥', 13.49, '13.49%'),
                  ('其他', 2.58, '2.58%')],
        'inner_derive': [('化工新材料', 66.69, 16.20), ('基础化工', 17.25, 13.87),
                         ('化肥', 13.49, 9.21), ('其他', 2.58, 12.52)],
        'note': '左图＝2026H1 分板块收入占比，右图＝毛利贡献占比（＝收入占比 × 板块毛利率逐项推算后归一化）。'
                '化工新材料以 66.69% 的收入贡献 73.2% 的毛利。各板块毛利率见上表。',
    },
    '002408': {
        'chart': 'chartMix',
        'name': '收入与毛利构成（2025·左右双环）',
        'outer': [('化工制造', 62.81, '62.81%'),
                  ('国外贸易', 37.19, '37.19%')],
        'inner_derive': [('化工制造', 62.81, 4.74), ('国外贸易', 37.19, 2.13)],
        'note': '左图＝2025 年分板块收入占比，右图＝毛利贡献占比（＝收入占比 × 板块毛利率逐项推算后归一化）。'
                '化工制造以 62.81% 的收入贡献 79.0% 的毛利，国外贸易以 37.19% 的收入仅贡献 21.0%。',
    },
    '600392': {
        'chart': 'chartMix',
        'name': '收入与毛利构成（2025·左右双环）',
        'outer': [('稀土产品', 94.1, '94.1%'),
                  ('锆钛及其他', 5.4, '5.4%')],
        'inner': [('稀土产品', 98.6, '98.6%（毛利贡献 15.69 亿元）'),
                  ('锆钛及其他', 1.4, '1.4%（毛利贡献 0.23 亿元）')],
        'note': '左图＝2025 年分产品收入占比，右图＝毛利贡献占比（按年报披露的分产品毛利贡献额 '
                '15.69 / 0.23 亿元计算）。“合计”行不作为扇区。',
    },
    '601118': {
        'chart': 'chartMix',
        'name': '收入与毛利构成（2025·左右双环）',
        # 【2026-10-16 升级】原条目只有单环，理由写的是「公司未按产品披露分项毛利率」。
        #   实测 iFinD「主营构成-按产品」**给到了**三项的毛利与毛利率，故补上右环。
        #   口径：2025 年报按产品前三档；三项收入合计 422.371 亿元
        #   = 合并营业收入 422.3715 亿元（**100% 覆盖**），加权毛利率 2.515% ≈ 合并 2.52%
        'outer': [('橡胶产品', 96.31, '96.31%'),
                  ('其他业务', 3.20, '3.20%'),
                  ('橡胶木材', 0.49, '0.49%')],
        'inner': [('橡胶产品', 61.09, '61.09%'),
                  ('其他业务', 35.75, '35.75%'),
                  ('橡胶木材', 3.16, '3.16%')],
        'note': '左图＝2025 年报分产品收入构成，右图＝毛利贡献构成（iFinD「主营构成-按产品」前三档；'
                '三项收入合计 <b>422.371 亿元</b>，与合并营业收入 <b>完全一致（100% 覆盖）</b>，'
                '加权毛利率 2.515% 亦与合并毛利率 2.52% 吻合）。'
                '★ <b>这张图回答的是「海南橡胶到底靠什么赚钱」</b>：'
                '<b>橡胶产品</b>拿走 <b>96.31%</b> 的收入，毛利却只占 <b>61.09%</b> —— '
                '毛利率 <b>1.60%</b>，主业几乎是「搬量不赚钱」；'
                '而<b>「其他业务」只用 3.20% 的收入贡献了 35.75% 的毛利</b>，'
                '毛利率 <b>28.13%</b>，是三项里最高的。<b>橡胶木材</b>收入 0.49%、毛利 3.16%'
                '（毛利率 16.17%），体量小却比主业赚钱。'
                '⇒ 一句话：<b>公司卖的是橡胶，赚的却不是橡胶的钱</b> —— '
                '主业是规模与战略基本盘，利润的近四成来自非胶业务。',
    },
    '601958': {
        'chart': 'chartMix',
        'name': '收入与毛利构成（2025·左右双环）',
        'outer': [('钼炉料', 65.42, '65.42%'),
                  ('钼金属', 15.85, '15.85%'),
                  ('钼化工', 12.81, '12.81%'),
                  ('其他', 5.26, '5.26%'),
                  ('其他业务', 0.65, '0.65%')],
        'inner_derive': [('钼炉料', 65.42, 39.74), ('钼金属', 15.85, 46.94),
                         ('钼化工', 12.81, 43.97), ('其他', 5.26, 36.31),
                         ('其他业务', 0.65, 21.62)],
        'assert_inner': {'钼炉料': (63.22, 0.3)},     # 与年报披露值对照（容差 0.3pct）
        'note': '左图＝2025 年分产品收入占比，右图＝毛利贡献占比（＝收入占比 × 产品毛利率逐项推算后归一化；'
                '钼炉料一项与年报披露的毛利占比 63.22% 吻合）。',
    },
    '603599': {
        'chart': 'chartMix',
        'name': '收入与毛利构成（2025·左右双环）',
        'outer': [('农药原药', 54.5, '54.5%'),
                  ('农药中间体及其他', 44.6, '44.6%'),
                  ('其他', 0.9, '0.9%')],
        'inner_derive': [('农药原药', 54.5, 34.72), ('农药中间体及其他', 44.6, 30.71)],
        'note': '左图＝2025 年分板块收入占比，右图＝毛利贡献占比（＝收入占比 × 板块毛利率逐项推算后归一化）。'
                '“其他（贸易及少量副产品）”占收入 0.9%、年报未单独披露毛利率，未纳入右图。',
    },
    '603977': {
        'chart': 'chartMix',
        'name': '收入与毛利构成（2025·左右双环）',
        'outer': [('民爆一体化', 65.5, '65.5%'),
                  ('军工新材料', 16.7, '16.7%'),
                  ('轨交自动化及信息化', 7.5, '7.5%'),
                  ('其他（含数字产业）', 10.3, '10.3%')],
        'inner_derive': [('民爆一体化', 65.5, 42.66), ('轨交自动化及信息化', 7.5, 42.59)],
        'note': '左图＝2025 年分板块收入占比，右图＝毛利贡献占比（＝收入占比 × 板块毛利率推算后归一化）。'
                '⚠️ 军工新材料（16.7%）与其他（10.3%）年报未单独披露板块毛利率、未纳入右图 —— '
                '右图覆盖 73.0% 的收入。',
    },
    # 2026-10-16 新增：雪峰科技 603227。左右两环均取自 iFinD「主营构成-按产品」的**披露值**
    # （m11 表格里的「占营业收入比」「占毛利贡献比」两列），不是推算值 —— 故走 inner 而非
    # inner_derive。LNG 2025 年毛利率 −5.64%、毛利贡献 −1.96%，按用户令「负数不显示」整条剔除。
    '603227': {
        'chart': 'chartMix',
        'name': '收入与毛利构成（2025·左右双环）',
        'outer': [('化工产品', 38.50, '38.50%'),
                  ('爆破服务', 36.31, '36.31%'),
                  ('民爆产品', 8.40, '8.40%'),
                  ('LNG', 7.49, '7.49%'),
                  ('商品贸易', 6.37, '6.37%')],
        # 顺序必须与 outer 一致（spec_check 会断言）：环颜色靠 index 对齐
        'inner': [('化工产品', 23.86, '23.86%'),
                  ('爆破服务', 51.70, '51.70%'),
                  ('民爆产品', 19.43, '19.43%'),
                  ('LNG', -1.96, '−1.96%（毛利率 −5.64%，毛利为负，按规定不在环上显示）', True),
                  ('商品贸易', 6.97, '6.97%')],
        'note': '左图＝2025 年分产品收入构成，右图＝毛利贡献构成（均为 iFinD「主营构成-按产品」'
                '披露口径，与上表两列逐项一致）。⚠️ <b>LNG 毛利为负</b>（毛利率 −5.64%、'
                '毛利贡献占比 −1.96%），按惯例<b>不在右图中显示</b>；剔除该项后右图四项按比例放大'
                '（四项原值合计 101.96%）。<b>爆破服务以 36.31% 的收入贡献 51.70% 的毛利</b>，'
                '是第一大毛利来源；<b>化工产品收入占比 38.50% 最高，但只贡献 23.86% 的毛利</b> —— '
                '这正是本报告「壁垒在民爆、波动在能化」的图形证据。',
    },
    '000762': {
        'chart': 'chartMix',
        'name': '收入与毛利构成（2025·左右双环）',
        'outer': [('铬铁矿', 53.30, '53.30%'),
                  ('锂精矿（普通）', 19.50, '19.50%'),
                  ('碳酸锂', 10.78, '10.78%'),
                  ('氯化钾', 8.12, '8.12%'),
                  ('锂精矿（立体）', 7.58, '7.58%')],
        # 顺序必须与 outer 一致（spec_check 会断言）：环颜色靠 index 对齐
        'inner': [('铬铁矿', 68.08, '68.08%'),
                  ('锂精矿（普通）', 31.07, '31.07%'),
                  ('碳酸锂', -1.07, '−1.07%（毛利率 −3.15%，毛利为负，按规定不在环上显示）', True),
                  ('氯化钾', 0.99, '0.99%'),
                  ('锂精矿（立体）', 0.93, '0.93%')],
        'note': '左图＝2025 年分产品收入构成，右图＝毛利贡献构成（均为 iFinD「主营构成-按产品」'
                '披露口径，与上表两列逐项一致）。⚠️ <b>碳酸锂毛利为负</b>（毛利率 −3.15%、'
                '毛利贡献占比 −1.07%）——这是 2025 年的状态，<b>2026H1 该业务毛利率已转正到 '
                '+54.18%</b>；按惯例负值项<b>不在右图中显示</b>（剔除后其余四项按比例放大）。'
                '<b>铬铁矿以 53.30% 的收入贡献 68.08% 的毛利</b>，是真正的现金牛；'
                '<b>锂精矿只用 19.50% 的收入就贡献 31.07% 的毛利</b>（毛利率 50.57%，五类最高）。'
                '⇒ <b>2025 年这家公司的利润几乎全部来自「铬 + 锂精矿」，二期碳酸锂还在亏钱爬坡</b>。',
    },
    '002237': {
        'chart': 'chartMix',
        'name': '收入与毛利构成（2025·左右双环）',
        'outer': [('黄金', 71.35, '71.35%'),
                  ('电解铜', 16.36, '16.36%'),
                  ('白银', 8.75, '8.75%'),
                  ('有色金属贸易', 2.23, '2.23%'),
                  ('电解铅', 1.31, '1.31%')],
        # 顺序必须与 outer 一致（spec_check 会断言）：环颜色靠 index 对齐
        'inner': [('黄金', 22.91, '22.91%'),
                  ('电解铜', 36.46, '36.46%'),
                  ('白银', 23.16, '23.16%'),
                  ('有色金属贸易', 0.51, '0.51%'),
                  ('电解铅', 16.95, '16.95%')],
        'note': '左图＝2025 年分产品收入构成，右图＝毛利贡献构成（iFinD「主营构成-按产品」2025 年报口径，'
                '前五档收入合计 1,088.18 亿元、占合并营收的 <b>96.82%</b>，与上表两列逐项一致）。'
                '★ <b>这张图是全篇最反直觉的一张</b>：<b>黄金拿走 71.35% 的收入，只留下 22.91% 的毛利</b>；'
                '而<b>电解铜 + 电解铅合计收入仅 17.67%，毛利却占到 53.41%</b>。'
                '⇒ 贵金属在这里不是利润来源，而是<b>流量入口</b>——真正的加工利润在铜铅与稀散金属回收。'
                '⚠️ 剩余 3.18% 收入（约 35.76 亿元）计入「其他业务」，其毛利率约 27.3%、'
                '<b>高于全部五大主产品</b>，但公司未披露明细 —— 这是本报告的一个已知数据缺口。',
    },
    '000731': {
        'chart': 'chartMix',
        'name': '收入与毛利构成（2026H1·左右双环）',
        # 口径：iFinD「主营构成-按行业」2026 半年报；四项合计 18.9115 亿元 = 合并营业收入（**100% 覆盖**）
        'outer': [('化学肥料制造业', 54.61, '54.61%'),
                  ('天然气供应', 25.93, '25.93%'),
                  ('贸易及其他', 19.20, '19.20%'),
                  ('房地产开发', 0.26, '0.26%')],
        # 顺序必须与 outer 一致（spec_check 会断言）：环颜色靠 index 对齐
        'inner': [('化学肥料制造业', 47.00, '47.00%'),
                  ('天然气供应', 18.78, '18.78%'),
                  ('贸易及其他', 33.97, '33.97%'),
                  ('房地产开发', 0.25, '0.25%')],
        'note': '左图＝2026H1 分行业收入构成，右图＝毛利贡献构成（iFinD「主营构成-按行业」，'
                '四项合计 <b>18.9115 亿元</b>，与合并营业收入<b>完全一致（100% 覆盖）</b>，'
                '与上方表格逐项一致）。★ <b>这张图纠正了一个容易想当然的判断</b>：'
                '<b>化肥是规模基本盘，但最赚钱的不是它</b> —— 化学肥料制造业拿走 <b>54.61%</b> 的收入，'
                '只留下 <b>47.00%</b> 的毛利（毛利率 7.19%）；而<b>「贸易及其他」用 19.20% 的收入'
                '贡献了 33.97% 的毛利</b>（毛利率 <b>14.78%</b>，是四大板块里最高的）。'
                '<b>天然气供应</b>收入 25.93%、毛利 18.78%（毛利率 6.05%），是典型的「过路费」业务：'
                '体量大、赚得薄。<b>房地产开发</b>收入与毛利均已压到 0.26%，基本退出。'
                '⇒ 一句话：<b>公司名义上是化肥企业，但增量利润正在向贸易与副产环节迁移</b>。',
    },
    # ⚠️ 600459 **刻意不进 SPEC** —— 它的 m11 是「表格版」设计（分板块收入与毛利表 +
    #   整体毛利率净利率趋势表），模块里只有 `data-chart="chartMargin"` 一个图槽，
    #   **没有 chartMix 槽**；而它自己的 chartMix 图表是「分板块收入 bar + 毛利率 line」
    #   （2026H1 口径，与上方表格逐项同源）。
    #   2026-10-16 曾试给它上双环，脚本报「未找到锚点 data-chart=\"chartMix\"」而失败 ——
    #   这正是**正确结果**：强上双环会把 2025 年报（分产品）与模块里的 2026H1（分板块）
    #   两个口径并排，读者会以为图与表是同一份数据。
    #   数据留档于此（2025 年报「主营构成-按产品」前五档，收入占比 → 毛利占比）：
    #     贵金属再生资源材料 37.43 → 38.17 ｜ 贵金属贸易 35.17 → 9.45
    #     贵金属特种功能材料 14.04 → 25.60 ｜ 贵金属前驱体材料 9.93 → 11.70
    #     机动车催化净化器 3.43 → 15.08
}


# ─────────────────────────── 基础工具 ───────────────────────────
def req(path, method='GET', body=None, timeout=120):
    data = json.dumps(body, ensure_ascii=False).encode('utf-8') if body is not None else None
    r = urllib.request.Request(REST + path, data=data, headers=HDR, method=method)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            raw = resp.read().decode('utf-8', 'replace')
            return resp.status, (json.loads(raw) if raw.strip() else None)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', 'replace')[:600]
    except Exception as e:
        return 0, str(e)


def pct1(x):
    """推算值统一保留一位小数 —— 一位小数本身就是「这是推算值、不是披露值」的视觉标记，
    不要按 scF1 那样把 .0 抹掉（抹掉后 79.0% 与 63.2% 精度看起来不一致）。"""
    return '%.1f%%' % x


def apply(rows):
    """把 (名, 值, tooltip[, 负]) 统一成 ECharts data 项。

    ★ 斜纹必须写成 `data[i].itemStyle.decal`，**不是** `data[i].decal` ——
      ECharts 的 decal 是 itemStyle 的子属性，写在数据项顶层会被静默忽略。
    ★ 底色仍走 series.color 数组（不受 beauty 重映射），这里只补 decal；
      decal 的 `backgroundColor` 在 **canvas 渲染器下生效**（2026-10-14 像素采样实测：
      白斜线 rgba(255,255,255,.95) + 绿底 #0b8a5c → 画布上真的交替出现 235,246,242 与
      11,138,92 两色）。注意它在 **SVG 渲染器下不生效**（zrender 的 pattern 生成器
      不吐背景矩形）—— 所以别用 SVG 渲染的截图判断斜纹好不好看。
    ★ `borderWidth:1` 是**必须的**：beauty() 给所有饼图扇区强加 2.5px 白色描边，
      而 600456 的负值扇区只占内环 2.03% 的弧长（半径 59px 时约 7.7px 宽），
      两侧各 2.5px 白边一吃就只剩 2.7px，斜纹等于看不见（首版截图就是这个症状）。
      数据项级 itemStyle 优先级高于系列级，所以这里压到 1px 是有效的。"""
    out = []
    for row in rows:
        name, val, tip = row[0], row[1], row[2]
        item = {'name': name, 'value': val, 'tip': tip}
        if len(row) > 3 and row[3]:
            item['itemStyle'] = {
                'borderWidth': 1,
                'decal': {
                    'symbol': 'rect', 'symbolSize': 1,
                    'dashArrayX': [1, 0], 'dashArrayY': [5, 5],
                    'rotation': -0.7854,
                    'color': 'rgba(255,255,255,.95)', 'backgroundColor': NEG}}
        out.append(item)
    return out


def derive(spec):
    """把 inner_derive（收入占比 × 毛利率）换算成归一化后的毛利贡献占比"""
    rows = []
    raw = []
    for name, share, gm in spec['inner_derive']:
        raw.append((name, share * gm))
    tot = sum(v for _, v in raw)
    for i, (name, v) in enumerate(raw):
        p = v / tot * 100
        rows.append((name, round(p, 1), pct1(p)))
    # 归一化后按原顺序返回；调用方再用 PAL 同序上色
    return rows


def drop_neg(rows):
    """★ 负值不显示（2026-10-14 用户令）。

    环上画不出负弧长 —— 上一版的做法是「取绝对值画弧 + 斜纹标记 + 真值进 tooltip」，
    用户看过实物后要求**直接不显示**。所以这里把带第 4 位（负值标记）的行整条剔除，
    不做绝对值、不加斜纹；被剔除的事实与真值写进图下注释（SPEC 的 note），
    **绝不改写成 0 也不悄悄翻正**。"""
    if not rows:
        return rows, []
    keep, gone = [], []
    for r in rows:
        (gone if (len(r) > 3 and r[3]) else keep).append(r)
    return keep, gone


def build_opt(spec):
    outer = apply([(n, v, t) for n, v, t in spec['outer']])
    if spec.get('inner') is not None:
        inner_rows = spec['inner']
    elif spec.get('inner_derive'):
        inner_rows = derive(spec)
    else:
        inner_rows = None
    inner_rows, _gone = drop_neg(inner_rows)

    # 左环：收入构成。有右环时靠左，否则（601118）居中并放大
    series = [{
        'name': '收入构成',
        'type': 'pie',
        'radius': RAD if inner_rows else RAD_ONE,
        'center': CEN_L if inner_rows else CEN_ONE,
        'color': PAL,
        # minMargin 给两行标签之间留最小间距；avoidLabelOverlap 默认开，配上更长的引线
        # 才能把 6.17% / 7.85% 这类相邻小扇区的标签真正拉开（而非叠在一起）。
        'label': {'formatter': LBL_FMT, 'minMargin': 6},
        'labelLine': {'length': 12, 'length2': 10, 'smooth': True},
        'data': outer,
    }]
    if inner_rows:
        # 右环颜色按「与左环同名同色」逐项对齐 ⇒ 同一个板块在两个环里是同一种颜色，
        # 读者不需要看图例就知道左右两块是同一件事。
        # ★ 只有这里是 index 对齐的：右环是左环的**子集且保持原顺序**时才成立，
        #   所以 SPEC 里 inner / inner_derive 的名字顺序必须与 outer 一致（下方有断言）。
        cmap = {}
        for i, (n, _, _) in enumerate(spec['outer']):
            cmap[n] = PAL[i % len(PAL)]
        cols = []
        for row in inner_rows:
            name = row[0]
            neg = len(row) > 3 and row[3]
            cols.append(NEG if neg else cmap.get(name, PAL[len(cols) % len(PAL)]))
        series.append({
            'name': '毛利构成',
            'type': 'pie',
            'radius': RAD,
            'center': CEN_R,
            'color': cols,
            'label': {'formatter': LBL_FMT, 'minMargin': 6},
            'labelLine': {'length': 12, 'length2': 10, 'smooth': True},
            'data': apply(inner_rows),
        })
    opt = {
        'legend': {'bottom': 0},
        'tooltip': {'trigger': 'item', 'formatter': '{{fn:ringTip}}'},
        'series': series,
    }
    if inner_rows:
        # 环下小标题：不用 graphic（见文件头第 3 条），改用 title 数组 ——
        # `left` 给百分比 + `textAlign:'center'` 让整块标题以该百分比为中心。
        opt['title'] = [
            {'text': CAP_L, 'left': CEN_L[0], 'bottom': CAP_BOTTOM, 'textAlign': 'center',
             'textStyle': {'fontSize': 12.5, 'fontWeight': 600, 'color': '#8c0a20'}},
            {'text': CAP_R, 'left': CEN_R[0], 'bottom': CAP_BOTTOM, 'textAlign': 'center',
             'textStyle': {'fontSize': 12.5, 'fontWeight': 600, 'color': '#8c0a20'}},
        ]
    return opt


# ─────────────────────── 模块 HTML 里的口径说明 ───────────────────────
NOTE_RE = re.compile(r'\s*<p class="muted" data-ringnote="1"[^>]*>.*?</p>', re.S)
NOTE_HTML = '<p class="muted" data-ringnote="1" style="font-size:12.5px;">%s</p>'


def sync_note(html, chart_key, text):
    """在 <div data-chart="KEY" …></div> 之后插入/替换口径说明（幂等）"""
    body = '<b>口径：</b>' + text
    html2 = NOTE_RE.sub('', html)                       # 先清掉旧说明
    anchor = re.compile(r'(<div data-chart="%s"[^>]*>\s*</div>)' % re.escape(chart_key))
    m = anchor.search(html2)
    if not m:
        return None, '未找到锚点 data-chart="%s"' % chart_key
    if len(anchor.findall(html2)) != 1:
        return None, '锚点 data-chart="%s" 出现 %d 次（预期 1 次）' % (
            chart_key, len(anchor.findall(html2)))
    pos = m.end(1)
    return html2[:pos] + '\n    ' + (NOTE_HTML % body) + html2[pos:], None


# ─────────────────── 定点重排：600456 的 m11 首屏（幂等） ───────────────────
# ★ 起因：600456 的 m11 首屏是 `.grid2` 两栏并排 ⇒ 图表槽位实测只有 **466×340**，
#   而其余 6 篇是 1010×360。同心双环时无所谓（一个环占半栏刚好），
#   但拆成**左右两个环**后，466px 里两环必然重叠、标签互相压（实测截图确认）。
# 做法：把那层 `.grid2` 与两个包裹 `<div>` 去掉，让两张图各自独占整行（槽位 ~1010px，
#   与其他研报一致），并把 chartGrossMix 的 `.chart-box short`(300px) 提到 `.chart-box`(360px)。
# 幂等：只在检测到该 `.grid2` 包裹时才动；尾巴不配对就**整体回滚**，绝不写坏结构。
RL_HEAD = re.compile(
    r'<div class="grid2">\s*<div>\s*(<h3>产品收入构成（2025）</h3>\s*'
    r'<div data-chart="chart2"[^>]*></div>)\s*</div>\s*<div>\s*')
RL_TAIL = re.compile(r'(<p class="muted" data-ringnote="1"[^>]*>.*?</p>)\s*</div>\s*</div>')
RL_OLD_BOX = '<div data-chart="chartGrossMix" class="chart-box short"></div>'
RL_NEW_BOX = '<div data-chart="chartGrossMix" class="chart-box"></div>'
RELAYOUT_CODES = {'600456'}


def relayout(code, html):
    """600456 专用：把 chart2 / chartGrossMix 从 .grid2 半栏里解放成整行。"""
    if code not in RELAYOUT_CODES:
        return html, None
    head, n1 = RL_HEAD.subn(r'\1\n    ', html, 1)
    n2 = 0
    if n1:
        tail, n2 = RL_TAIL.subn(r'\1', head, 1)
        if not n2:                     # 尾巴没配对 ⇒ 回滚，绝不写坏结构
            return html, None
        head = tail
    out, n3 = head, 0
    if RL_OLD_BOX in out:
        out = out.replace(RL_OLD_BOX, RL_NEW_BOX, 1)
        n3 = 1
    if not n1 and not n3:
        return html, None
    return out, '拆平 grid2=%d 尾巴=%d 放大槽位=%d' % (n1, n2, n3)


# ─────────────────────────── 主流程 ───────────────────────────
def spec_check():
    """规格自检：右环名字必须还在左环里、且顺序与左环一致（颜色靠 index 对齐）"""
    bad = []
    for code, sp in SPEC.items():
        onames = [r[0] for r in sp['outer']]
        if sp.get('inner') is not None:
            irows = sp['inner']
        elif sp.get('inner_derive'):
            irows = derive(sp)
        else:
            irows = None
        irows, _ = drop_neg(irows)
        if not irows:
            continue
        for r in irows:
            if r[0] not in onames:
                bad.append('%s 右环「%s」不在左环里' % (code, r[0]))
        idx = [onames.index(r[0]) for r in irows]
        if idx != sorted(idx):
            bad.append('%s 右环顺序与左环不一致（颜色会串）' % code)
        # 左环颜色唯一性：扇区数 ≤ 7 才可能有唯一色
        if len(onames) > len(PAL):
            bad.append('%s 左环 %d 项 > 调色板 %d 色' % (code, len(onames), len(PAL)))
    return bad


# ── 附带定点修正：让 m11 左右两张图的名字口径一致 ──
# 600456 左边那张「产品收入构成」环图（chart2）的扇区名写的是「其他产品」，
# 而 m11 表格与新的内环都写「其他金属产品」—— 两图并排时同一个板块出现两个名字，
# 用户看到的就是「同一个东西两套叫法」。只改这一个字符串，数值 / 配色 / 结构一律不动。
SIDE = {
    '600456_chart2': [('其他产品', '其他金属产品')],
}


def run_side(now, mode):
    """执行 SIDE 里的定点修正（幂等：命中才改）"""
    for cid, pairs in SIDE.items():
        st, rows = req('wb_report_charts?id=eq.%s&select=id,opt' % cid)
        if st >= 400 or not isinstance(rows, list) or not rows:
            print('%-20s ✗ 侧车修正读取失败 %s %s' % (cid, st, rows))
            return 1
        opt = rows[0]['opt']
        blob = json.dumps(opt, ensure_ascii=False)
        todo = [(a, b) for a, b in pairs if a in blob]
        if not todo:
            print('%-20s · 侧车修正已是目标形态（无「%s」）'
                  % (cid, '」/「'.join(a for a, _ in pairs)))
            continue
        new = json.loads(blob)
        for a, b in todo:
            new = json.loads(json.dumps(new, ensure_ascii=False).replace(a, b))
            print('%-20s · 侧车修正：扇区名「%s」→「%s」' % (cid, a, b))
        if mode != 'apply':
            continue
        st2, r2 = req('wb_report_charts?id=eq.%s' % cid, 'PATCH', {'opt': new, 'up': now})
        if st2 >= 400:
            print('%-20s ✗ 侧车修正写库失败 %s %s' % (cid, st2, r2))
            return 1
        print('%-20s ✓ 已写入（http %s）' % (cid, st2))
    return 0


def main():
    mode = 'apply'
    if '--dry' in sys.argv:
        mode = 'dry'
    elif '--check' in sys.argv:
        mode = 'check'

    # --only <code[,code]>：只处理指定标的。新增研报时用 —— 不加本参数时行为与从前完全一致
    # （全量 8 份 + 侧车修正），避免「给新研报补规格」顺手重写其他已上线的报告。
    only = None
    if '--only' in sys.argv:
        only = set(x.strip() for x in sys.argv[sys.argv.index('--only') + 1].split(',') if x.strip())
        unknown = only - set(SPEC)
        if unknown:
            print('✗ --only 里有 SPEC 不认识的标的：%s' % ','.join(sorted(unknown)))
            return 1

    # --emit <path>：只把「将要写入的配置」导出成 JSON 给预览探针用，不碰库
    if '--emit' in sys.argv:
        path = sys.argv[sys.argv.index('--emit') + 1]
        payload = {code: {'chart': sp['chart'], 'name': sp['name'], 'opt': build_opt(sp)}
                   for code, sp in sorted(SPEC.items()) if not only or code in only}
        io.open(path, 'w', encoding='utf-8').write(
            json.dumps(payload, ensure_ascii=False, indent=1))
        n2 = sum(1 for v in payload.values() if len(v['opt']['series']) > 1)
        print('已导出 %d 份配置 → %s（双环 %d · 单环 %d）'
              % (len(payload), path, n2, len(payload) - n2))
        return 0

    bad = spec_check()
    if bad:
        print('✗ 规格自检失败：')
        for b in bad:
            print('   · ' + b)
        return 1

    # 年报披露值对照（601958：推算 vs 披露）
    for code, sp in SPEC.items():
        for name, (disc, tol) in (sp.get('assert_inner') or {}).items():
            got = [r[1] for r in derive(sp) if r[0] == name]
            if got and abs(got[0] - disc) > tol:
                print('✗ %s「%s」推算 %.2f%% 与披露 %.2f%% 差 %.2f pct，超出容差 —— 公式核对后再写库'
                      % (code, name, got[0], disc, abs(got[0] - disc)))
                return 1
            if got:
                print('✓ %s「%s」推算 %.1f%% ≈ 年报披露 %.2f%%（容差内）'
                      % (code, name, got[0], disc))

    print('=' * 104)
    print('目标：%d 份研报的 m11 结构图 → 左右双环（%s）'
          % (len(SPEC), {'dry': '试运行，不写库', 'check': '只读校验', 'apply': '写库'}[mode]))
    print('=' * 104)

    now = int(time.time() * 1000)
    if not only and run_side(now, mode):        # --only 时跳过侧车修正（它只针对 600456）
        return 1
    print('-' * 104)
    ok = skip = fail = 0
    for code in sorted(SPEC):
        if only and code not in only:
            continue
        sp = SPEC[code]
        cid = '%s_%s' % (code, sp['chart'])
        want = build_opt(sp)
        st, rows = req('wb_report_charts?id=eq.%s&select=id,opt,name' % cid)
        if st >= 400 or not isinstance(rows, list) or not rows:
            print('%-8s ✗ 读图表失败 %s %s' % (code, st, rows)); fail += 1; continue
        cur = rows[0]['opt']
        inner_n = len(want['series'][1]['data']) if len(want['series']) > 1 else 0
        head = '%-8s %-14s 外环 %d 项' % (code, sp['chart'], len(want['series'][0]['data']))
        head += ('· 内环 %d 项' % inner_n) if inner_n else '· 单环（分项毛利率未披露）'

        if cur == want and rows[0].get('name') == sp['name']:
            print(head + '  → 已是目标形态，跳过')
            same_opt = True
        else:
            same_opt = False
            print(head)
            for s in want['series']:
                print('        · %-6s radius=%s color=%s' % (s['name'], s['radius'], s['color']))
            for d in want['series'][-1]['data']:
                tag = ''
                if 'decal' in d:
                    tag = ' ⟍斜纹'
                print('            %-12s value=%-8s tip=%s%s' % (d['name'], d['value'], d['tip'], tag))

        st, mods = req('wb_report_mods?report_id=eq.%s&no=eq.11&select=id,html' % code)
        if st >= 400 or not isinstance(mods, list) or not mods:
            print('   ✗ 读 m11 模块失败 %s %s' % (st, mods)); fail += 1; continue
        mrow = mods[0]
        html = mrow.get('html') or ''
        new_html, err = sync_note(html, sp['chart'], sp['note'])
        if err:
            print('   ✗ 模块说明注入失败：%s' % err); fail += 1; continue
        if sp.get('retitle'):
            old, new = sp['retitle']
            if old in new_html:
                new_html = new_html.replace(old, new, 1)
                print('   · h3 改名：%s → %s' % (old[4:-5], new[4:-5]))
            elif new not in new_html:
                print('   ⚠️ h3 未命中（可能已改过）：%s' % old[4:-5])
        new_html, rl = relayout(code, new_html)
        if rl:
            print('   · 版式重排：%s' % rl)

        if mode == 'dry':
            print('   · 模块说明将插入到 data-chart="%s" 之后：%s' % (sp['chart'], sp['note'][:60] + '…'))
            print('   [dry] 不写库')
        elif mode == 'check':
            if not same_opt:
                print('   ✗ 图表 opt 与规格不一致'); fail += 1
            elif new_html != html:
                print('   ✗ 模块说明与规格不一致'); fail += 1
            else:
                ok += 1
        else:
            if not same_opt:
                st1, r1 = req('wb_report_charts?id=eq.%s' % cid, 'PATCH',
                              {'opt': want, 'name': sp['name'], 'up': now})
                if st1 >= 400:
                    print('   ✗ 图表写库失败 %s %s' % (st1, r1)); fail += 1; continue
                print('   ✓ 图表 opt 已写入（http %s）' % st1)
            if new_html != html:
                bd = os.path.join(HERE, 'backup')          # ★ 写前必留回滚副本
                os.makedirs(bd, exist_ok=True)
                bp = os.path.join(bd, 'ring_%s_m11_%s.json'
                                  % (code, time.strftime('%Y%m%d-%H%M%S')))
                io.open(bp, 'w', encoding='utf-8').write(json.dumps(
                    {'code': code, 'id': mrow['id'], 'html': html,
                     'opt': cur, 'name': rows[0].get('name')}, ensure_ascii=False))
                print('   · 旧稿已备份 → backup/%s' % os.path.basename(bp))
                st2, r2 = req('wb_report_mods?id=eq.%s' % mrow['id'], 'PATCH',
                              {'html': new_html, 'up': now})
                if st2 >= 400:
                    print('   ✗ 模块写库失败 %s %s' % (st2, r2)); fail += 1; continue
                st9, rb = req('wb_report_mods?id=eq.%s&select=html' % mrow['id'])
                print('   ✓ m11 已写入（http %s）· 回读逐字节一致：%s'
                      % (st2, st9 == 200 and rb[0]['html'] == new_html))
            ok += 1
        print('-' * 104)

    print('=' * 104)
    if mode == 'check':
        print('校验：%d 篇一致 · %d 篇不一致' % (ok, fail))
    elif mode == 'dry':
        print('试运行完成（未写库）· 失败 %d' % fail)
    else:
        print('完成：%d 篇已就绪 · 失败 %d' % (ok, fail))
    return 1 if fail else 0


if __name__ == '__main__':
    sys.exit(main())
