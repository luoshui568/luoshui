-- ============================================================
-- 删除前的二次确认预检：拿 token + 密码换一个明确的是/否
-- 前端先用它校验，避免走完整删除流程后再报错
-- ============================================================

CREATE OR REPLACE FUNCTION public.wb_admin_verify(p_token text, p_pass text)
RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp
AS $$
DECLARE
  v_ok  jsonb;
  v_row public.wb_admins%ROWTYPE;
BEGIN
  v_ok := public.wb_admin_check(p_token);
  IF NOT (v_ok->>'ok')::boolean THEN RETURN v_ok; END IF;

  IF coalesce(p_pass,'') = '' THEN
    RETURN jsonb_build_object('ok', false, 'code', 'NOPASS', 'msg', '请输入管理员密码');
  END IF;

  SELECT * INTO v_row FROM public.wb_admins WHERE user_name = v_ok->>'user' LIMIT 1;
  IF NOT FOUND OR v_row.pass_hash IS NULL
     OR v_row.pass_hash <> crypt(p_pass, v_row.pass_hash) THEN
    RETURN jsonb_build_object('ok', false, 'code', 'BADPASS', 'msg', '密码错误，操作已取消');
  END IF;

  RETURN jsonb_build_object('ok', true, 'user', v_row.user_name);
END $$;

GRANT EXECUTE ON FUNCTION public.wb_admin_verify(text,text) TO anon, authenticated;
