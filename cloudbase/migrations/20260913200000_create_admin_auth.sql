-- ============================================================
-- 服务端超级管理员认证（阶段 A：建表 + 建函数，不动既有权限）
-- 目标：账号密码存数据库、bcrypt 哈希、登录签发 token、
--       所有校验走 SECURITY DEFINER 函数，anon 无法读哈希
-- ============================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ---------- 1. 管理员账号表 ----------
CREATE TABLE IF NOT EXISTS public.wb_admins (
  id           text PRIMARY KEY,
  user_name    text NOT NULL UNIQUE,
  display_name text DEFAULT '',
  pass_hash    text NOT NULL,
  role         text DEFAULT 'super',
  status       text DEFAULT 'active',
  last_login   timestamptz,
  login_count  integer DEFAULT 0,
  note         text DEFAULT '',
  t            bigint,
  up           bigint
);

-- ---------- 2. 登录会话表 ----------
CREATE TABLE IF NOT EXISTS public.wb_admin_sessions (
  token      text PRIMARY KEY,
  user_name  text NOT NULL,
  device     text DEFAULT '',
  created_at timestamptz DEFAULT now(),
  expire_at  timestamptz NOT NULL,
  revoked    boolean DEFAULT false
);

CREATE INDEX IF NOT EXISTS wb_admin_sessions_user_idx   ON public.wb_admin_sessions (user_name);
CREATE INDEX IF NOT EXISTS wb_admin_sessions_expire_idx ON public.wb_admin_sessions (expire_at);

-- ---------- 3. 锁死两表：给 anon 不下发任何 policy ----------
-- anon 角色没有 RLS policy → 既读不到 pass_hash，也改不了。
-- SECURITY DEFINER 函数以建表者（owner，绕过 RLS）身份运行，可以正常读写。
ALTER TABLE public.wb_admins           ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.wb_admin_sessions   ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.wb_admins         FROM anon, authenticated;
REVOKE ALL ON public.wb_admin_sessions FROM anon, authenticated;

-- ---------- 4. 登录 ----------
CREATE OR REPLACE FUNCTION public.wb_admin_login(
  p_user   text,
  p_pass   text,
  p_device text DEFAULT '',
  p_days   integer DEFAULT 7
) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp
AS $$
DECLARE
  v_row   public.wb_admins%ROWTYPE;
  v_token text;
  v_days  integer;
BEGIN
  v_days := greatest(1, least(90, coalesce(p_days, 7)));

  SELECT * INTO v_row FROM public.wb_admins
   WHERE lower(user_name) = lower(btrim(coalesce(p_user,''))) LIMIT 1;

  IF NOT FOUND THEN
    RETURN jsonb_build_object('ok', false, 'code', 'BADCRED', 'msg', '账号或密码错误');
  END IF;
  IF v_row.status <> 'active' THEN
    RETURN jsonb_build_object('ok', false, 'code', 'DISABLED', 'msg', '该账号已被停用，请联系管理员');
  END IF;
  IF v_row.pass_hash IS NULL OR v_row.pass_hash <> crypt(coalesce(p_pass,''), v_row.pass_hash) THEN
    RETURN jsonb_build_object('ok', false, 'code', 'BADCRED', 'msg', '账号或密码错误');
  END IF;

  v_token := encode(gen_random_bytes(24), 'hex');
  INSERT INTO public.wb_admin_sessions(token, user_name, device, expire_at)
  VALUES (v_token, v_row.user_name, left(coalesce(p_device,''),120), now() + (v_days || ' days')::interval);

  UPDATE public.wb_admins
     SET last_login = now(), login_count = coalesce(login_count,0) + 1, up = (extract(epoch from now())*1000)::bigint
   WHERE id = v_row.id;

  DELETE FROM public.wb_admin_sessions WHERE expire_at < now() - interval '2 days';

  RETURN jsonb_build_object(
    'ok', true, 'token', v_token,
    'user', v_row.user_name,
    'name', coalesce(nullif(v_row.display_name,''), v_row.user_name),
    'role', coalesce(v_row.role,'super'),
    'days', v_days,
    'expire', to_char(now() + (v_days || ' days')::interval, 'YYYY-MM-DD HH24:MI')
  );
END $$;

-- ---------- 5. 校验 token ----------
CREATE OR REPLACE FUNCTION public.wb_admin_check(p_token text)
RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp
AS $$
DECLARE v_s public.wb_admin_sessions%ROWTYPE;
BEGIN
  IF p_token IS NULL OR length(p_token) < 16 THEN
    RETURN jsonb_build_object('ok', false, 'code', 'NOTOKEN', 'msg', '未提供有效凭证');
  END IF;
  SELECT * INTO v_s FROM public.wb_admin_sessions WHERE token = p_token LIMIT 1;
  IF NOT FOUND THEN
    RETURN jsonb_build_object('ok', false, 'code', 'NOSESSION', 'msg', '登录已失效，请重新登录');
  END IF;
  IF v_s.revoked THEN
    RETURN jsonb_build_object('ok', false, 'code', 'REVOKED', 'msg', '该登录已被注销，请重新登录');
  END IF;
  IF v_s.expire_at < now() THEN
    RETURN jsonb_build_object('ok', false, 'code', 'EXPIRED', 'msg', '登录已过期，请重新登录');
  END IF;
  RETURN jsonb_build_object('ok', true, 'user', v_s.user_name,
                            'expire', to_char(v_s.expire_at, 'YYYY-MM-DD HH24:MI'));
END $$;

-- ---------- 6. 退出登录 ----------
CREATE OR REPLACE FUNCTION public.wb_admin_logout(p_token text)
RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp
AS $$
BEGIN
  UPDATE public.wb_admin_sessions SET revoked = true WHERE token = p_token;
  RETURN jsonb_build_object('ok', true);
END $$;

-- ---------- 7. 修改密码 ----------
CREATE OR REPLACE FUNCTION public.wb_admin_change_pass(p_token text, p_old text, p_new text)
RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp
AS $$
DECLARE
  v_s   public.wb_admin_sessions%ROWTYPE;
  v_row public.wb_admins%ROWTYPE;
BEGIN
  SELECT * INTO v_s FROM public.wb_admin_sessions
   WHERE token = coalesce(p_token,'') AND NOT revoked AND expire_at > now() LIMIT 1;
  IF NOT FOUND THEN
    RETURN jsonb_build_object('ok', false, 'code', 'NOSESSION', 'msg', '登录已失效，请重新登录');
  END IF;
  IF length(coalesce(p_new,'')) < 6 THEN
    RETURN jsonb_build_object('ok', false, 'code', 'WEAK', 'msg', '新密码至少 6 位');
  END IF;

  SELECT * INTO v_row FROM public.wb_admins WHERE user_name = v_s.user_name LIMIT 1;
  IF NOT FOUND THEN
    RETURN jsonb_build_object('ok', false, 'code', 'NOUSER', 'msg', '账号不存在');
  END IF;
  IF v_row.pass_hash <> crypt(coalesce(p_old,''), v_row.pass_hash) THEN
    RETURN jsonb_build_object('ok', false, 'code', 'BADPASS', 'msg', '当前密码不正确');
  END IF;

  UPDATE public.wb_admins
     SET pass_hash = crypt(p_new, gen_salt('bf', 10)),
         up = (extract(epoch from now())*1000)::bigint
   WHERE id = v_row.id;

  -- 改密后注销其它设备上的会话，保留当前这一个
  UPDATE public.wb_admin_sessions SET revoked = true
   WHERE user_name = v_row.user_name AND token <> p_token;

  RETURN jsonb_build_object('ok', true, 'msg', '密码已更新');
END $$;

-- ---------- 8. 管理员列表（脱敏，不含哈希） ----------
CREATE OR REPLACE FUNCTION public.wb_admin_list(p_token text)
RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp
AS $$
DECLARE v_ok jsonb;
BEGIN
  v_ok := public.wb_admin_check(p_token);
  IF NOT (v_ok->>'ok')::boolean THEN RETURN v_ok; END IF;
  RETURN jsonb_build_object('ok', true, 'rows', coalesce((
    SELECT jsonb_agg(jsonb_build_object(
      'user_name', user_name,
      'display_name', coalesce(display_name,''),
      'role', coalesce(role,'super'),
      'status', coalesce(status,'active'),
      'last_login', case when last_login is null then '' else to_char(last_login,'YYYY-MM-DD HH24:MI') end,
      'login_count', coalesce(login_count,0)
    ) ORDER BY user_name)
    FROM public.wb_admins), '[]'::jsonb));
END $$;

-- ---------- 9. 新建管理员 ----------
CREATE OR REPLACE FUNCTION public.wb_admin_create(p_token text, p_user text, p_pass text, p_name text DEFAULT '')
RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp
AS $$
DECLARE v_ok jsonb; v_u text;
BEGIN
  v_ok := public.wb_admin_check(p_token);
  IF NOT (v_ok->>'ok')::boolean THEN RETURN v_ok; END IF;
  v_u := lower(btrim(coalesce(p_user,'')));
  IF length(v_u) < 3 THEN RETURN jsonb_build_object('ok', false, 'msg', '账号至少 3 个字符'); END IF;
  IF length(coalesce(p_pass,'')) < 6 THEN RETURN jsonb_build_object('ok', false, 'msg', '密码至少 6 位'); END IF;
  IF EXISTS (SELECT 1 FROM public.wb_admins WHERE lower(user_name) = v_u) THEN
    RETURN jsonb_build_object('ok', false, 'msg', '该账号已存在');
  END IF;
  INSERT INTO public.wb_admins(id, user_name, display_name, pass_hash, role, status, t, up)
  VALUES ('a-' || v_u, v_u, coalesce(nullif(btrim(p_name),''), v_u),
          crypt(p_pass, gen_salt('bf', 10)), 'ops', 'active',
          (extract(epoch from now())*1000)::bigint, (extract(epoch from now())*1000)::bigint);
  RETURN jsonb_build_object('ok', true, 'msg', '已创建');
END $$;

-- ---------- 10. 停用 / 启用 / 删除管理员 ----------
CREATE OR REPLACE FUNCTION public.wb_admin_set_status(p_token text, p_user text, p_status text)
RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp
AS $$
DECLARE v_ok jsonb; v_me text;
BEGIN
  v_ok := public.wb_admin_check(p_token);
  IF NOT (v_ok->>'ok')::boolean THEN RETURN v_ok; END IF;
  v_me := v_ok->>'user';
  IF lower(p_user) = lower(v_me) THEN
    RETURN jsonb_build_object('ok', false, 'msg', '不能停用自己当前登录的账号');
  END IF;
  IF p_status NOT IN ('active','disabled') THEN
    RETURN jsonb_build_object('ok', false, 'msg', '状态非法');
  END IF;
  UPDATE public.wb_admins SET status = p_status, up = (extract(epoch from now())*1000)::bigint
   WHERE lower(user_name) = lower(btrim(p_user));
  IF p_status = 'disabled' THEN
    UPDATE public.wb_admin_sessions SET revoked = true WHERE lower(user_name) = lower(btrim(p_user));
  END IF;
  RETURN jsonb_build_object('ok', true, 'msg', case when p_status='disabled' then '已停用' else '已启用' end);
END $$;

CREATE OR REPLACE FUNCTION public.wb_admin_delete(p_token text, p_user text)
RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp
AS $$
DECLARE v_ok jsonb; v_me text; v_u text; v_n integer;
BEGIN
  v_ok := public.wb_admin_check(p_token);
  IF NOT (v_ok->>'ok')::boolean THEN RETURN v_ok; END IF;
  v_me := v_ok->>'user';
  v_u  := lower(btrim(coalesce(p_user,'')));
  IF v_u = lower(v_me) THEN
    RETURN jsonb_build_object('ok', false, 'msg', '不能删除自己当前登录的账号');
  END IF;
  IF (SELECT count(*) FROM public.wb_admins) <= 1 THEN
    RETURN jsonb_build_object('ok', false, 'msg', '至少保留一个管理员账号');
  END IF;
  DELETE FROM public.wb_admins WHERE lower(user_name) = v_u;
  GET DIAGNOSTICS v_n = ROW_COUNT;
  DELETE FROM public.wb_admin_sessions WHERE lower(user_name) = v_u;
  RETURN jsonb_build_object('ok', v_n > 0, 'msg', case when v_n > 0 then '已删除' else '账号不存在' end);
END $$;

-- ---------- 11. 服务端删除数据行（白名单表） ----------
CREATE OR REPLACE FUNCTION public.wb_admin_delete_row(p_token text, p_kind text, p_id text)
RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp
AS $$
DECLARE v_ok jsonb; v_tbl text; v_n integer;
BEGIN
  v_ok := public.wb_admin_check(p_token);
  IF NOT (v_ok->>'ok')::boolean THEN RETURN v_ok; END IF;

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

-- ---------- 12. 授权：anon 只能「调用函数」，不能直读表 ----------
GRANT EXECUTE ON FUNCTION public.wb_admin_login(text,text,text,integer)      TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.wb_admin_check(text)                       TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.wb_admin_logout(text)                      TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.wb_admin_change_pass(text,text,text)       TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.wb_admin_list(text)                        TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.wb_admin_create(text,text,text,text)       TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.wb_admin_set_status(text,text,text)        TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.wb_admin_delete(text,text)                 TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.wb_admin_delete_row(text,text,text)        TO anon, authenticated;

-- ---------- 13. 种子管理员：luoshui / 981208 ----------
INSERT INTO public.wb_admins (id, user_name, display_name, pass_hash, role, status, note, t, up)
VALUES ('a-luoshui', 'luoshui', '超级管理员',
        crypt('981208', gen_salt('bf', 10)), 'super', 'active', '初始超级管理员',
        (extract(epoch from now())*1000)::bigint, (extract(epoch from now())*1000)::bigint)
ON CONFLICT (user_name) DO NOTHING;
