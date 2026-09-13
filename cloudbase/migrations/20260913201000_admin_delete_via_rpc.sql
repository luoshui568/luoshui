-- ============================================================
-- 阶段 B：删除操作收归服务端
-- 1) wb_admin_delete_row 增加 p_pass 参数 —— 删除必须同时带 token + 管理员密码
-- 2) REVOKE DELETE ON 7 张业务表 FROM anon, authenticated
--    → 浏览器再也无法绕过前端直接删库，删除只能走上面这个函数
-- ============================================================

DROP FUNCTION IF EXISTS public.wb_admin_delete_row(text, text, text);

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

-- ---------- 收回直删权限 ----------
REVOKE DELETE ON public.wb_tasks      FROM anon, authenticated;
REVOKE DELETE ON public.wb_permits    FROM anon, authenticated;
REVOKE DELETE ON public.wb_milestones FROM anon, authenticated;
REVOKE DELETE ON public.wb_watchlist  FROM anon, authenticated;
REVOKE DELETE ON public.wb_contacts   FROM anon, authenticated;
REVOKE DELETE ON public.wb_logs       FROM anon, authenticated;
REVOKE DELETE ON public.wb_works      FROM anon, authenticated;
