-- ============================================================
-- 普通管理员自助注册 + 超级管理员批准（阶段 C）
-- 目标：
--   1) 登录页开放「注册普通管理员」，申请落库为 status='pending'；
--   2) 只有超级管理员（role='super'）能查看待批列表并批准 / 驳回；
--      批准动作必须复核超级管理员密码（wb_admin_verify）；
--   3) 收紧既有管理员函数：非 super 一律拒（NOPERM），堵住提权；
--   4) wb_admin_check 额外回传 role，前端可随时校正自己的角色。
--
-- 状态机：pending（待批准）→ active（可用）
--                        → rejected（已驳回，保留留痕，可由超管删除后重新注册）
--         active ↔ disabled（停用/启用）
-- ============================================================

-- ---------- 0. 申请表字段 ----------
ALTER TABLE public.wb_admins ADD COLUMN IF NOT EXISTS reg_note text DEFAULT '';
ALTER TABLE public.wb_admins ADD COLUMN IF NOT EXISTS reg_at   timestamptz;
ALTER TABLE public.wb_admins ADD COLUMN IF NOT EXISTS reg_by   text DEFAULT '';

CREATE INDEX IF NOT EXISTS wb_admins_status_idx ON public.wb_admins (status);

-- ---------- 1. 内部辅助：当前 token 是不是超级管理员 ----------
CREATE OR REPLACE FUNCTION public.wb_admin_is_super(p_token text)
RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp
AS $$
DECLARE v_ok jsonb; v_role text;
BEGIN
  v_ok := public.wb_admin_check(p_token);
  IF NOT coalesce((v_ok->>'ok')::boolean, false) THEN RETURN false; END IF;
  SELECT coalesce(role,'') INTO v_role FROM public.wb_admins
   WHERE lower(user_name) = lower(v_ok->>'user') LIMIT 1;
  RETURN coalesce(v_role,'') = 'super';
END $$;

-- ---------- 2. 校验 token（增加 role 回传 + 账号被删/停用即失效） ----------
CREATE OR REPLACE FUNCTION public.wb_admin_check(p_token text)
RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp
AS $$
DECLARE
  v_s    public.wb_admin_sessions%ROWTYPE;
  v_role text;
  v_st   text;
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

  SELECT coalesce(role,'ops'), coalesce(status,'active') INTO v_role, v_st
    FROM public.wb_admins WHERE lower(user_name) = lower(v_s.user_name) LIMIT 1;
  IF NOT FOUND THEN
    RETURN jsonb_build_object('ok', false, 'code', 'NOUSER', 'msg', '账号已不存在，请重新登录');
  END IF;
  IF v_st <> 'active' THEN
    RETURN jsonb_build_object('ok', false, 'code', 'DISABLED', 'msg',
      case v_st when 'pending'  then '账号正在等待超级管理员批准'
                when 'rejected' then '注册申请未通过，请联系超级管理员'
                else '该账号已被停用，请联系管理员' end);
  END IF;

  RETURN jsonb_build_object('ok', true, 'user', v_s.user_name, 'role', v_role,
                            'expire', to_char(v_s.expire_at, 'YYYY-MM-DD HH24:MI'));
END $$;

-- ---------- 3. 登录（区分 待批准 / 已驳回 / 已停用） ----------
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

  /* 密码先验：避免用账号状态去探测「哪些账号存在」 */
  IF v_row.pass_hash IS NULL OR v_row.pass_hash <> crypt(coalesce(p_pass,''), v_row.pass_hash) THEN
    RETURN jsonb_build_object('ok', false, 'code', 'BADCRED', 'msg', '账号或密码错误');
  END IF;

  IF v_row.status = 'pending' THEN
    RETURN jsonb_build_object('ok', false, 'code', 'PENDING',
      'msg', '注册申请正在等待超级管理员批准，通过后即可登录');
  END IF;
  IF v_row.status = 'rejected' THEN
    RETURN jsonb_build_object('ok', false, 'code', 'REJECTED',
      'msg', '该注册申请未通过，请联系超级管理员');
  END IF;
  IF v_row.status <> 'active' THEN
    RETURN jsonb_build_object('ok', false, 'code', 'DISABLED', 'msg', '该账号已被停用，请联系管理员');
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
    'role', coalesce(v_row.role,'ops'),
    'days', v_days,
    'expire', to_char(now() + (v_days || ' days')::interval, 'YYYY-MM-DD HH24:MI')
  );
END $$;

-- ---------- 4. 自助注册普通管理员（anon 可调，落 pending） ----------
CREATE OR REPLACE FUNCTION public.wb_admin_register(
  p_user text,
  p_pass text,
  p_name text DEFAULT '',
  p_note text DEFAULT ''
) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp
AS $$
DECLARE v_u text; v_n integer;
BEGIN
  v_u := lower(btrim(coalesce(p_user,'')));
  IF v_u !~ '^[a-z0-9_]{3,24}$' THEN
    RETURN jsonb_build_object('ok', false, 'code', 'BADUSER',
      'msg', '账号需为 3-24 位小写字母 / 数字 / 下划线');
  END IF;
  IF length(coalesce(p_pass,'')) < 6 THEN
    RETURN jsonb_build_object('ok', false, 'code', 'WEAK', 'msg', '密码至少 6 位');
  END IF;
  IF EXISTS (SELECT 1 FROM public.wb_admins WHERE lower(user_name) = v_u) THEN
    RETURN jsonb_build_object('ok', false, 'code', 'EXISTS',
      'msg', '该账号已被占用（可能已存在或已在审批中），请换一个');
  END IF;

  /* 防灌：待批准申请不允许无限堆积 */
  SELECT count(*) INTO v_n FROM public.wb_admins WHERE coalesce(status,'') = 'pending';
  IF v_n >= 20 THEN
    RETURN jsonb_build_object('ok', false, 'code', 'TOOMANY',
      'msg', '待批准的申请过多，请稍后再试或直接联系超级管理员');
  END IF;

  INSERT INTO public.wb_admins(id, user_name, display_name, pass_hash, role, status,
                               note, reg_note, reg_at, t, up)
  VALUES ('a-' || v_u, v_u, coalesce(nullif(btrim(p_name),''), v_u),
          crypt(p_pass, gen_salt('bf', 10)), 'ops', 'pending',
          '自助注册待批准', left(coalesce(p_note,''),160), now(),
          (extract(epoch from now())*1000)::bigint, (extract(epoch from now())*1000)::bigint);

  RETURN jsonb_build_object('ok', true, 'code', 'PENDING',
    'msg', '申请已提交，等超级管理员批准后即可登录');
END $$;

-- ---------- 5. 待批准列表（仅超级管理员） ----------
CREATE OR REPLACE FUNCTION public.wb_admin_pending_list(p_token text)
RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp
AS $$
DECLARE v_ok jsonb;
BEGIN
  v_ok := public.wb_admin_check(p_token);
  IF NOT coalesce((v_ok->>'ok')::boolean, false) THEN RETURN v_ok; END IF;
  IF NOT public.wb_admin_is_super(p_token) THEN
    RETURN jsonb_build_object('ok', false, 'code', 'NOPERM',
      'msg', '仅超级管理员可查看待批准申请');
  END IF;
  RETURN jsonb_build_object('ok', true, 'rows', coalesce((
    SELECT jsonb_agg(jsonb_build_object(
      'user_name',    user_name,
      'display_name', coalesce(display_name,''),
      'reg_note',     coalesce(reg_note,''),
      'reg_at',       case when reg_at is null then '' else to_char(reg_at,'YYYY-MM-DD HH24:MI') end
    ) ORDER BY reg_at)
    FROM public.wb_admins WHERE coalesce(status,'') = 'pending'), '[]'::jsonb));
END $$;

-- ---------- 6. 批准 / 驳回（仅超级管理员，且必须复核密码） ----------
CREATE OR REPLACE FUNCTION public.wb_admin_review(
  p_token  text,
  p_user   text,
  p_action text,
  p_pass   text
) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp
AS $$
DECLARE
  v_ok  jsonb;
  v_ver jsonb;
  v_u   text;
  v_me  text;
  v_n   integer;
BEGIN
  v_ok := public.wb_admin_check(p_token);
  IF NOT coalesce((v_ok->>'ok')::boolean, false) THEN RETURN v_ok; END IF;
  IF NOT public.wb_admin_is_super(p_token) THEN
    RETURN jsonb_build_object('ok', false, 'code', 'NOPERM',
      'msg', '仅超级管理员可批准或驳回注册申请');
  END IF;

  /* 关键动作必须复核密码：只校验、不消费 */
  v_ver := public.wb_admin_verify(p_token, p_pass);
  IF NOT coalesce((v_ver->>'ok')::boolean, false) THEN
    RETURN jsonb_build_object('ok', false,
      'code', coalesce(v_ver->>'code','BADPASS'),
      'msg',  coalesce(nullif(v_ver->>'msg',''), '密码校验未通过，操作已取消'));
  END IF;

  v_u  := lower(btrim(coalesce(p_user,'')));
  v_me := v_ok->>'user';
  /* approve 允许对「待批准」或「已驳回」操作（超管可以改主意）；reject 只针对待批准 */
  UPDATE public.wb_admins
     SET status = case when p_action = 'approve' then 'active' else 'rejected' end,
         reg_by = v_me,
         up     = (extract(epoch from now())*1000)::bigint
   WHERE lower(user_name) = v_u
     AND (case when p_action = 'approve'
               then coalesce(status,'') in ('pending','rejected')
               else coalesce(status,'') = 'pending' end);
  GET DIAGNOSTICS v_n = ROW_COUNT;

  IF v_n = 0 THEN
    RETURN jsonb_build_object('ok', false, 'msg', '该申请不存在或已被处理');
  END IF;
  RETURN jsonb_build_object('ok', true, 'action', p_action,
    'msg', case when p_action = 'approve'
                then '已批准「' || v_u || '」，该账号现在可以登录（登录后进入「投资标的」）'
                else '已驳回「' || v_u || '」的注册申请' end);
END $$;

-- ---------- 7. 管理员列表：super 看全部，其它只看自己 ----------
CREATE OR REPLACE FUNCTION public.wb_admin_list(p_token text)
RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp
AS $$
DECLARE v_ok jsonb; v_sup boolean; v_me text;
BEGIN
  v_ok := public.wb_admin_check(p_token);
  IF NOT coalesce((v_ok->>'ok')::boolean, false) THEN RETURN v_ok; END IF;
  v_sup := public.wb_admin_is_super(p_token);
  v_me  := v_ok->>'user';
  RETURN jsonb_build_object('ok', true, 'scope', case when v_sup then 'all' else 'self' end,
    'rows', coalesce((
    SELECT jsonb_agg(jsonb_build_object(
      'user_name', user_name,
      'display_name', coalesce(display_name,''),
      'role', coalesce(role,'ops'),
      'status', coalesce(status,'active'),
      'reg_note', coalesce(reg_note,''),
      'last_login', case when last_login is null then '' else to_char(last_login,'YYYY-MM-DD HH24:MI') end,
      'login_count', coalesce(login_count,0)
    ) ORDER BY role DESC, user_name)
    FROM public.wb_admins
    WHERE v_sup OR lower(user_name) = lower(v_me)), '[]'::jsonb));
END $$;

-- ---------- 8. 新建 / 停用 / 删除：一律限超级管理员 ----------
CREATE OR REPLACE FUNCTION public.wb_admin_create(p_token text, p_user text, p_pass text, p_name text DEFAULT '')
RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp
AS $$
DECLARE v_ok jsonb; v_u text;
BEGIN
  v_ok := public.wb_admin_check(p_token);
  IF NOT coalesce((v_ok->>'ok')::boolean, false) THEN RETURN v_ok; END IF;
  IF NOT public.wb_admin_is_super(p_token) THEN
    RETURN jsonb_build_object('ok', false, 'code', 'NOPERM', 'msg', '仅超级管理员可新增管理员账号');
  END IF;
  v_u := lower(btrim(coalesce(p_user,'')));
  IF v_u !~ '^[a-z0-9_]{3,24}$' THEN
    RETURN jsonb_build_object('ok', false, 'msg', '账号需为 3-24 位小写字母 / 数字 / 下划线');
  END IF;
  IF length(coalesce(p_pass,'')) < 6 THEN RETURN jsonb_build_object('ok', false, 'msg', '密码至少 6 位'); END IF;
  IF EXISTS (SELECT 1 FROM public.wb_admins WHERE lower(user_name) = v_u) THEN
    RETURN jsonb_build_object('ok', false, 'msg', '该账号已存在');
  END IF;
  INSERT INTO public.wb_admins(id, user_name, display_name, pass_hash, role, status, note, t, up)
  VALUES ('a-' || v_u, v_u, coalesce(nullif(btrim(p_name),''), v_u),
          crypt(p_pass, gen_salt('bf', 10)), 'ops', 'active', '超级管理员直接创建',
          (extract(epoch from now())*1000)::bigint, (extract(epoch from now())*1000)::bigint);
  RETURN jsonb_build_object('ok', true, 'msg', '已创建。该账号登录后直接进入「投资标的」');
END $$;

CREATE OR REPLACE FUNCTION public.wb_admin_set_status(p_token text, p_user text, p_status text)
RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp
AS $$
DECLARE v_ok jsonb; v_me text; v_n integer;
BEGIN
  v_ok := public.wb_admin_check(p_token);
  IF NOT coalesce((v_ok->>'ok')::boolean, false) THEN RETURN v_ok; END IF;
  IF NOT public.wb_admin_is_super(p_token) THEN
    RETURN jsonb_build_object('ok', false, 'code', 'NOPERM', 'msg', '仅超级管理员可停用 / 启用账号');
  END IF;
  v_me := v_ok->>'user';
  IF lower(btrim(coalesce(p_user,''))) = lower(v_me) THEN
    RETURN jsonb_build_object('ok', false, 'msg', '不能停用自己当前登录的账号');
  END IF;
  IF p_status NOT IN ('active','disabled') THEN
    RETURN jsonb_build_object('ok', false, 'msg', '状态非法');
  END IF;
  UPDATE public.wb_admins SET status = p_status, up = (extract(epoch from now())*1000)::bigint
   WHERE lower(user_name) = lower(btrim(p_user));
  GET DIAGNOSTICS v_n = ROW_COUNT;
  IF v_n = 0 THEN RETURN jsonb_build_object('ok', false, 'msg', '账号不存在'); END IF;
  IF p_status = 'disabled' THEN
    UPDATE public.wb_admin_sessions SET revoked = true WHERE lower(user_name) = lower(btrim(p_user));
  END IF;
  RETURN jsonb_build_object('ok', true, 'msg', case when p_status='disabled' then '已停用' else '已启用' end);
END $$;

CREATE OR REPLACE FUNCTION public.wb_admin_delete(p_token text, p_user text)
RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp
AS $$
DECLARE v_ok jsonb; v_me text; v_u text; v_n integer; v_keep integer;
BEGIN
  v_ok := public.wb_admin_check(p_token);
  IF NOT coalesce((v_ok->>'ok')::boolean, false) THEN RETURN v_ok; END IF;
  IF NOT public.wb_admin_is_super(p_token) THEN
    RETURN jsonb_build_object('ok', false, 'code', 'NOPERM', 'msg', '仅超级管理员可删除账号');
  END IF;
  v_me := v_ok->>'user';
  v_u  := lower(btrim(coalesce(p_user,'')));
  IF v_u = lower(v_me) THEN
    RETURN jsonb_build_object('ok', false, 'msg', '不能删除自己当前登录的账号');
  END IF;
  /* 至少留下一个可用的超级管理员，避免把自己锁在门外 */
  SELECT count(*) INTO v_keep FROM public.wb_admins
   WHERE coalesce(role,'') = 'super' AND coalesce(status,'') = 'active' AND lower(user_name) <> v_u;
  IF v_keep = 0 THEN
    RETURN jsonb_build_object('ok', false, 'msg', '必须保留至少一个启用中的超级管理员');
  END IF;
  DELETE FROM public.wb_admins WHERE lower(user_name) = v_u;
  GET DIAGNOSTICS v_n = ROW_COUNT;
  DELETE FROM public.wb_admin_sessions WHERE lower(user_name) = v_u;
  RETURN jsonb_build_object('ok', true, 'msg', case when v_n > 0 then '已删除' else '账号不存在' end);
END $$;

-- ---------- 9. 授权 ----------
GRANT EXECUTE ON FUNCTION public.wb_admin_register(text,text,text,text)   TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.wb_admin_pending_list(text)              TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.wb_admin_review(text,text,text,text)     TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.wb_admin_check(text)                     TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.wb_admin_login(text,text,text,integer)   TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.wb_admin_list(text)                      TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.wb_admin_create(text,text,text,text)     TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.wb_admin_set_status(text,text,text)      TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.wb_admin_delete(text,text)               TO anon, authenticated;
-- wb_admin_is_super 只做内部判定，不下发 execute 权限，前端调不到
