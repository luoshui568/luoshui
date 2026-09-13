-- 投资标的：增加「人工锁定字段」与「基本面刷新时间」
--
-- lock_fields：逗号分隔的字段名。用户在「编辑标的」里手动改过的字段会被登记在这里，
--              云端每日同步与浏览器「同步行情」都会跳过这些字段，避免把人工填的值冲掉。
-- info_at    ：基本面（行业PE / 细分行业 / 总资产 / 地区）最近一次自动刷新的时间。

ALTER TABLE public.wb_stocks ADD COLUMN IF NOT EXISTS lock_fields text DEFAULT '';
ALTER TABLE public.wb_stocks ADD COLUMN IF NOT EXISTS info_at timestamptz;

COMMENT ON COLUMN public.wb_stocks.lock_fields IS '人工锁定字段（逗号分隔），自动同步时跳过';
COMMENT ON COLUMN public.wb_stocks.info_at IS '基本面字段（行业PE/细分行业/总资产/地区）最近刷新时间';
