-- ============================================================
-- 投资标的（二级市场股票池）：行情 + 基本面快照
-- 1) 新建 wb_stocks，19 个展示字段与用户截图表格一一对应
-- 2) RLS：anon 可读可写，但【不给 DELETE】—— 删除统一走 wb_admin_delete_row
-- 3) 重定义 wb_admin_delete_row，把 stocks 纳入白名单
--
-- 单位约定（前端统一格式化，避免各处换算不一致）：
--   amount / mkt_cap                → 元      （显示时折成 亿/万）
--   total_assets / net_assets       → 亿元    （与截图列名「总资产(亿)」一致）
--   所有 *_pct / chg_* / div_yield  → 数值本身（-3.86 即 -3.86%）
-- ============================================================

CREATE TABLE IF NOT EXISTS public.wb_stocks (
  id            text PRIMARY KEY,
  code          text NOT NULL,                    -- 6 位纯数字，如 600459
  name          text DEFAULT '',                  -- 名称
  exchange      text DEFAULT 'sh',                -- sh / sz / bj / hk
  chg_pct       numeric(12,3),                    -- 涨幅%
  price         numeric(14,4),                    -- 现价
  amount        numeric(22,2),                    -- 总金额（元）
  ind_pe        numeric(12,3),                    -- 行业PE
  pe_fwd        numeric(14,3),                    -- 市盈(动)
  pe_ttm        numeric(14,3),                    -- 市盈(TTM)
  pb            numeric(12,3),                    -- 市净率
  div_yield     numeric(10,3),                    -- 股息率%
  mkt_cap       numeric(22,2),                    -- 总市值（元）
  chg_ytd       numeric(10,3),                    -- 年初至今%
  chg_10d       numeric(10,3),                    -- 10 日涨幅%
  chg_20d       numeric(10,3),                    -- 20 日涨幅%
  chg_60d       numeric(10,3),                    -- 60 日涨幅%
  sub_industry  text DEFAULT '',                  -- 细分行业
  total_assets  numeric(20,2),                    -- 总资产（亿元）
  net_assets    numeric(20,2),                    -- 净资产（亿元）
  region        text DEFAULT '',                  -- 地区（省份）
  grp           text DEFAULT '',                  -- 自定义分组（贵金属/铜/稀土…）
  note          text DEFAULT '',                  -- 备注 / 投资逻辑
  sort          integer DEFAULT 99,               -- 排序
  quote_date    text DEFAULT '',                  -- 行情日期 YYYY-MM-DD
  quote_time    text DEFAULT '',                  -- 行情时间戳 YYYYMMDDHHMMSS
  sync_at       timestamptz,                      -- 最近一次同步时间
  t             bigint,
  up            bigint
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_wb_stocks_code ON public.wb_stocks (code);
CREATE INDEX IF NOT EXISTS idx_wb_stocks_grp ON public.wb_stocks (grp);

ALTER TABLE public.wb_stocks ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS wb_stocks_all ON public.wb_stocks;
CREATE POLICY wb_stocks_all ON public.wb_stocks
  FOR ALL TO anon, authenticated USING (true) WITH CHECK (true);

-- 【重要】不给 DELETE：删除只能通过服务端 wb_admin_delete_row（校验 token + 管理员密码）
GRANT SELECT, INSERT, UPDATE ON public.wb_stocks TO anon, authenticated;


-- ------------------------------------------------------------
-- 把 stocks 纳入服务端删除白名单
-- ------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.wb_admin_delete_row(
  p_token text,
  p_kind  text,
  p_id    text,
  p_pass  text
) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp
AS $$
DECLARE
  v_ok  jsonb;
  v_tbl text;
  v_n   integer;
  v_row public.wb_admins%ROWTYPE;
BEGIN
  v_ok := public.wb_admin_check(p_token);
  IF NOT (v_ok->>'ok')::boolean THEN RETURN v_ok; END IF;

  -- 二次确认：必须带正确密码
  IF coalesce(p_pass,'') = '' THEN
    RETURN jsonb_build_object('ok', false, 'code', 'NOPASS', 'msg', '请输入管理员密码');
  END IF;
  SELECT * INTO v_row FROM public.wb_admins WHERE user_name = v_ok->>'user' LIMIT 1;
  IF NOT FOUND OR v_row.pass_hash IS NULL
     OR v_row.pass_hash <> crypt(p_pass, v_row.pass_hash) THEN
    RETURN jsonb_build_object('ok', false, 'code', 'BADPASS', 'msg', '密码错误，删除已取消');
  END IF;

  v_tbl := CASE p_kind
    WHEN 'tasks'      THEN 'wb_tasks'
    WHEN 'permits'    THEN 'wb_permits'
    WHEN 'milestones' THEN 'wb_milestones'
    WHEN 'watch'      THEN 'wb_watchlist'
    WHEN 'contacts'   THEN 'wb_contacts'
    WHEN 'logs'       THEN 'wb_logs'
    WHEN 'works'      THEN 'wb_works'
    WHEN 'stocks'     THEN 'wb_stocks'
    ELSE NULL END;
  IF v_tbl IS NULL THEN
    RETURN jsonb_build_object('ok', false, 'msg', '不支持的数据类型：' || coalesce(p_kind,'?'));
  END IF;
  IF p_id IS NULL OR p_id = '' THEN
    RETURN jsonb_build_object('ok', false, 'msg', '缺少记录 ID');
  END IF;

  EXECUTE format('DELETE FROM public.%I WHERE id = $1', v_tbl) USING p_id;
  GET DIAGNOSTICS v_n = ROW_COUNT;
  RETURN jsonb_build_object('ok', true, 'deleted', v_n, 'table', v_tbl);
END $$;

GRANT EXECUTE ON FUNCTION public.wb_admin_delete_row(text,text,text,text) TO anon, authenticated;
