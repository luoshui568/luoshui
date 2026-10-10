# -*- coding: utf-8 -*-
"""iFinD MCP 服务管家：向 ~/.workbuddy/mcp.json 增/改 iFinD 服务。
密钥来源优先级：已有配置里的 Authorization → .workbuddy/tmp_ifind_token.txt
用法：
    python ifind_add.py                     # 写入 4 路官方服务（默认）
    python ifind_add.py stock fund index    # 只写指定几路
    python ifind_add.py --list              # 列出全部可选服务
"""
import io, json, os, sys

CFG = r'C:\Users\50522\.workbuddy\mcp.json'
TOKF = r'C:\Users\50522\WorkBuddy\2026-09-10-14-50-38\.workbuddy\tmp_ifind_token.txt'
HOST = 'https://api-mcp.51ifind.com:8643/ds-mcp-servers/'

# key → (slug, 中文名, 说明, 是否官方生成配置默认给的四路)
ALL = {
    'stock':  ('hexin-ifind-ds-stock-mcp',  'A股数据',      '个股摘要/选股/日频行情/资料/股本股东/财务/风险/事件/ESG/高频', True),
    'fund':   ('hexin-ifind-ds-fund-mcp',   '基金数据',      '选基/资料/业绩/份额持有人/持仓/财报/基金公司/高频',          True),
    'edb':    ('hexin-ifind-ds-edb-mcp',    '宏观行业指标',  '全球与中国宏观、行业经济指标 数值查询 + 指标搜索',            True),
    'news':   ('hexin-ifind-ds-news-mcp',   '公告新闻',      '公告语义检索 / 财经新闻 / 热点事件资讯',                      True),
    'bond':   ('hexin-ifind-ds-bond-mcp',   '债券',          '债券基本资料/行情估值/发债主体财务/信用评级/高频',            False),
    'index':  ('hexin-ifind-ds-index-mcp',  '指数与板块',    '股票指数/板块（行业·概念）指标 + 高频行情',                   False),
    'quote':  ('hexin-ifind-ds-quote-mcp',  '实时行情',      '股/基/债/指 实时快照高频 + 美股·港股实时行情',                False),
}


def get_token():
    try:
        cfg = json.load(io.open(CFG, encoding='utf-8'))
        for v in (cfg.get('mcpServers') or {}).values():
            a = (v.get('headers') or {}).get('Authorization')
            if a and a.count('.') == 4:      # JWE 形状
                return a
    except Exception:
        pass
    if os.path.exists(TOKF):
        return io.open(TOKF, encoding='utf-8').read().strip()
    raise SystemExit('找不到密钥：请先把 key 放到 %s' % TOKF)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if '--list' in sys.argv:
        for k, (slug, cn, d, dflt) in ALL.items():
            print('  %-7s %-14s %-12s %s' % (k, slug, cn, '官方默认' if dflt else '额外可开'))
        return 0
    keys = args or [k for k, v in ALL.items() if v[3]]
    bad = [k for k in keys if k not in ALL]
    if bad:
        raise SystemExit('未知服务 %s；可选：%s' % (bad, ', '.join(ALL)))

    tok = get_token()
    cfg = json.load(io.open(CFG, encoding='utf-8'))
    srv = cfg.setdefault('mcpServers', {})
    for k in keys:
        slug, cn, desc, _ = ALL[k]
        srv[slug] = {
            'type': 'streamableHttp',
            'url': HOST + slug,
            'headers': {'Authorization': tok},      # 官方形状：裸 JWE，不带 Bearer
            'timeout': 60000,
            'description': '同花顺 iFinD MCP · %s — %s' % (cn, desc),
            'disabled': False,
        }
        print('  + %-26s %s' % (slug, cn))
    io.open(CFG, 'w', encoding='utf-8', newline='\n').write(
        json.dumps(cfg, ensure_ascii=False, indent=2) + '\n')
    print('写入 %s' % CFG)
    print('服务清单: %s' % ', '.join(srv.keys()))
    print('提示：写完需在「连接器管理 → 自定义 MCP」点 Trust 才会生效。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
