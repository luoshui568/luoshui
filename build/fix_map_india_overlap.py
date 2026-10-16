# -*- coding: utf-8 -*-
"""把 `lib/world-cn.js` 里 India 的几何裁掉与中国重叠的部分。

═══════════════════════════════════════════════════════════════════════
为什么要这个脚本（2026-10-14 用户令）
═══════════════════════════════════════════════════════════════════════
用户：「台湾并入、藏南不划给印度、含港澳、含九段线，我现在用的地图这块
有没有问题，如果有问题直接帮我改地图」

`build/check_map_compliance.py` 实测结论：四条红线**视觉全部通过** ——
  ✓ 台湾在 China 内    ✓ 藏南 7 个采样点全在 China 内
  ✓ 港澳在 China 内    ✓ 南海有 9 段极细长形状（＝九段线）
  ✓ 阿克赛钦属 China   ✓ 分省底图含「南海诸岛」单元

**但发现一处数据层面的残留**：India 的几何仍覆盖藏南（lon 91~97 一带，
最北到 lat 28.12）。视觉上之所以正确，是因为 `make_worldmap.py` 把 China
挪到 features **末尾**（后绘制 ⇒ 压住印度在藏南的着色）—— 这是有意为之的
兜底，但**数据没裁干净**：一旦绘制顺序变化或做点选/高亮，就会露出来。

本脚本用几何差集（India − China）把它裁干净，做到**数据与视觉一致**。
重叠 = 0.60 平方度（占印度 0.23%），全部是藏南 + 克什米尔接触带。

用法：
    python3 build/fix_map_india_overlap.py --dry     # 只看差多少，不写盘
    python3 build/fix_map_india_overlap.py           # 备份 → 裁 → 写回 → 自检
"""
import io
import json
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(HERE, 'lib', 'world-cn.js')
BAK = os.path.join(HERE, 'backup')
KEY = "registerMap('worldcn',"
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from shapely.geometry import Point, mapping, shape          # noqa: E402
from shapely import set_precision                            # noqa: E402

#: 藏南采样点（用于裁剪前后自检；都在 lon 91~97, lat 27~29 的争议带）
ZANGNAN = [(92.0, 27.8), (91.8, 27.9), (93.5, 28.3), (94.5, 27.6),
           (95.0, 28.6), (96.5, 28.6), (97.0, 28.0)]


def rnd(c):
    """坐标收敛到 2 位小数（与文件全篇一致，防止 float64 长尾）。"""
    if isinstance(c[0], (int, float)):
        return [round(float(c[0]), 2), round(float(c[1]), 2)]
    return [rnd(x) for x in c]


def main():
    dry = '--dry' in sys.argv
    src = io.open(LIB, encoding='utf-8').read()

    i = src.index(KEY)
    st = src.index('{', i)
    dec = json.JSONDecoder()
    W, ln = dec.raw_decode(src[st:])
    old_json = src[st:st + ln]

    feats = {str(f['properties'].get('name')): f for f in W['features']}
    india, china = feats['India'], feats['China']

    g_cn = shape(china['geometry']).buffer(0)
    g_in = shape(india['geometry']).buffer(0)
    diff = set_precision(g_in.difference(g_cn), 0.01)

    print('India 原面积      : %.4f 平方度（%s，%d 个子多边形）'
          % (g_in.area, india['geometry']['type'],
             len(india['geometry']['coordinates']) if india['geometry']['type'] == 'MultiPolygon' else 1))
    print('与中国重叠        : %.4f 平方度（%.3f%%）' % (g_in.area - diff.area,
                                                        (g_in.area - diff.area) / g_in.area * 100))
    print('裁剪后 India      : %.4f 平方度（%s）' % (diff.area, diff.geom_type))

    before = [diff.contains(Point(x, y)) for x, y in ZANGNAN]
    print('裁剪后仍覆盖藏南  : %d / %d 点' % (sum(before), len(before)))
    assert not any(before), '裁剪失败：India 仍覆盖藏南'

    if dry:
        print('\n[dry] 未写盘。')
        return 0

    # ---- 备份 ----
    os.makedirs(BAK, exist_ok=True)
    ts = time.strftime('%Y%m%d-%H%M%S')
    bak = os.path.join(BAK, 'world-cn_%s.js' % ts)
    shutil.copy2(LIB, bak)
    print('\n已备份 → %s' % os.path.relpath(bak, HERE))

    # ---- 替换 India 几何 ----
    m = mapping(diff)
    geom = {'type': m['type'], 'coordinates': rnd(m['coordinates'])}
    india['geometry'] = geom

    new_json = json.dumps(W, ensure_ascii=False, separators=(',', ':'))
    out = src[:st] + new_json + src[st + ln:]
    io.open(LIB, 'w', encoding='utf-8').write(out)

    print('已写回 %s' % os.path.relpath(LIB, HERE))
    print('  文件 %d → %d 字符（%+d）' % (len(src), len(out), len(out) - len(src)))
    print('  India 几何 %s → %s' % (india['geometry']['type'], diff.geom_type))
    print('\n★ 下一步：python3 build/check_map_compliance.py 复核；'
          '改完必须重新构建并部署 report.html（地图在页面里）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
