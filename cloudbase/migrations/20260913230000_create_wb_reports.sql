-- ============================================================
-- 深度研究报告（多页面）：一份研报 = 元信息 + N 个模块 + M 张图表
-- 1) wb_reports       研报元信息（hero / 核心结论 / KPI / 目录 / 一句话本质 / 页脚）
-- 2) wb_report_mods   模块（编号 + 标题 + 正文 HTML，正文里用 <div data-chart="x"> 占位挂图）
-- 3) wb_report_charts 图表（ECharts option 原样存 JSON，函数以 {{fn:xxx}} 具名标记表示）
--
-- 设计要点：
--   · 图表 = 数据，不是代码 —— option 存库，前端只负责渲染，改数字不用改代码
--   · 模块正文存 HTML 片段 —— 段落/表格/列表/评分条都在里面，改文案不用改代码
--   · 三张表主键统一叫 id（研报的 id 就是股票代码），这样能复用同一个通用删除函数
--   · RLS：anon 可读可写，但【不给 DELETE】—— 删除统一走 wb_admin_delete_row
-- ============================================================

CREATE TABLE IF NOT EXISTS public.wb_reports (
  id            text PRIMARY KEY,                 -- 研报 id（当前 = 股票代码，如 600456）
  code          text NOT NULL,                    -- 对应股票代码
  name          text DEFAULT '',                  -- 公司简称
  kicker        text DEFAULT '',                  -- hero 顶部小字
  title         text DEFAULT '',                  -- hero 主标题
  subtitle      text DEFAULT '',                  -- hero 副标题
  badges        jsonb DEFAULT '[]'::jsonb,        -- hero 徽标数组（字符串）
  verdict_title text DEFAULT '核心结论',
  verdict_html  text DEFAULT '',                  -- 核心结论正文（HTML）
  kpis          jsonb DEFAULT '[]'::jsonb,        -- [{label,val,unit,cls}]
  kpi_note      text DEFAULT '',
  toc           jsonb DEFAULT '[]'::jsonb,        -- [{anchor,text}]
  essence_html  text DEFAULT '',                  -- 一句话本质（可证伪命题）
  footer_html   text DEFAULT '',
  theme         text DEFAULT 'red',               -- 主题（当前固定 red）
  sort          integer DEFAULT 99,
  up            bigint,
  t             timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.wb_report_mods (
  id        text PRIMARY KEY,                     -- <报告id>_m<编号>
  report_id text NOT NULL,                        -- 所属研报 = wb_reports.id
  code      text DEFAULT '',                      -- 冗余一份股票代码，便于按代码查
  seq       integer DEFAULT 0,
  no        text DEFAULT '',                      -- 模块编号（1..23）
  title     text DEFAULT '',
  html      text DEFAULT '',                      -- 模块正文（不含 h2，含 data-chart 占位）
  up        bigint,
  t         timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.wb_report_charts (
  id        text PRIMARY KEY,                     -- <报告id>_<图表id>
  report_id text NOT NULL,                        -- 所属研报 = wb_reports.id
  code      text DEFAULT '',                      -- 冗余一份股票代码
  seq       integer DEFAULT 0,
  name      text DEFAULT '',                      -- 图表名称（编辑器里显示）
  opt       jsonb NOT NULL DEFAULT '{}'::jsonb,   -- ECharts option
  up        bigint,
  t         timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_wb_reports_code       ON public.wb_reports (code);
CREATE INDEX IF NOT EXISTS idx_wb_report_mods_rep    ON public.wb_report_mods (report_id, seq);
CREATE INDEX IF NOT EXISTS idx_wb_report_charts_rep  ON public.wb_report_charts (report_id, seq);

ALTER TABLE public.wb_reports       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.wb_report_mods   ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.wb_report_charts ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS wb_reports_all ON public.wb_reports;
CREATE POLICY wb_reports_all ON public.wb_reports
  FOR ALL TO anon, authenticated USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS wb_report_mods_all ON public.wb_report_mods;
CREATE POLICY wb_report_mods_all ON public.wb_report_mods
  FOR ALL TO anon, authenticated USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS wb_report_charts_all ON public.wb_report_charts;
CREATE POLICY wb_report_charts_all ON public.wb_report_charts
  FOR ALL TO anon, authenticated USING (true) WITH CHECK (true);

-- 【重要】不给 DELETE：删除只能通过服务端 wb_admin_delete_row（校验 token + 管理员密码）
GRANT SELECT, INSERT, UPDATE ON public.wb_reports       TO anon, authenticated;
GRANT SELECT, INSERT, UPDATE ON public.wb_report_mods   TO anon, authenticated;
GRANT SELECT, INSERT, UPDATE ON public.wb_report_charts TO anon, authenticated;


-- ------------------------------------------------------------
-- 把 report / reportmod / reportchart 纳入服务端删除白名单
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
    WHEN 'tasks'       THEN 'wb_tasks'
    WHEN 'permits'     THEN 'wb_permits'
    WHEN 'milestones'  THEN 'wb_milestones'
    WHEN 'watch'       THEN 'wb_watchlist'
    WHEN 'contacts'    THEN 'wb_contacts'
    WHEN 'logs'        THEN 'wb_logs'
    WHEN 'works'       THEN 'wb_works'
    WHEN 'stocks'      THEN 'wb_stocks'
    WHEN 'report'      THEN 'wb_reports'
    WHEN 'reportmod'   THEN 'wb_report_mods'
    WHEN 'reportchart' THEN 'wb_report_charts'
    ELSE NULL END;
  IF v_tbl IS NULL THEN
    RETURN jsonb_build_object('ok', false, 'msg', '不支持的数据类型：' || coalesce(p_kind,'?'));
  END IF;
  IF p_id IS NULL OR p_id = '' THEN
    RETURN jsonb_build_object('ok', false, 'msg', '缺少记录 ID');
  END IF;

  -- 删整份研报时，连带它的模块与图表一起清掉（仍然已校验过管理员密码）
  IF p_kind = 'report' THEN
    DELETE FROM public.wb_report_charts WHERE report_id = p_id;
    DELETE FROM public.wb_report_mods   WHERE report_id = p_id;
  END IF;

  EXECUTE format('DELETE FROM public.%I WHERE id = $1', v_tbl) USING p_id;
  GET DIAGNOSTICS v_n = ROW_COUNT;
  RETURN jsonb_build_object('ok', true, 'deleted', v_n, 'table', v_tbl);
END $$;

GRANT EXECUTE ON FUNCTION public.wb_admin_delete_row(text,text,text,text) TO anon, authenticated;
