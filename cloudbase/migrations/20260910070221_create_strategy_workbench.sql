CREATE TABLE IF NOT EXISTS public.wb_tasks (
  id text PRIMARY KEY,
  seq integer,
  task_date text,
  weekday text,
  week_no integer,
  week_theme text,
  week_goal text,
  phase text,
  phase_name text,
  category text,
  title text,
  detail text,
  deliverable text,
  minutes integer,
  priority text,
  status text DEFAULT 'todo',
  note text,
  t bigint,
  up bigint
);

CREATE TABLE IF NOT EXISTS public.wb_permits (
  id text PRIMARY KEY,
  seq integer,
  code text,
  name text,
  category text,
  authority text,
  phase text,
  prereq text,
  materials text,
  duration text,
  cost text,
  risk text,
  priority text,
  status text DEFAULT '未启动',
  progress integer DEFAULT 0,
  owner text,
  due_date text,
  notes text,
  t bigint,
  up bigint
);

CREATE TABLE IF NOT EXISTS public.wb_milestones (
  id text PRIMARY KEY,
  seq integer,
  due_date text,
  title text,
  criteria text,
  phase text,
  status text DEFAULT '未启动',
  progress integer DEFAULT 0,
  t bigint,
  up bigint
);

CREATE TABLE IF NOT EXISTS public.wb_watchlist (
  id text PRIMARY KEY,
  name text,
  code text,
  variety text,
  style text,
  market text,
  thesis text,
  note text,
  status text,
  tags text,
  progress integer DEFAULT 0,
  sort integer DEFAULT 99,
  t bigint,
  up bigint
);

CREATE TABLE IF NOT EXISTS public.wb_contacts (
  id text PRIMARY KEY,
  role_name text,
  kind text,
  value text,
  org text,
  phase_plan text,
  note text,
  status text,
  t bigint,
  up bigint
);

CREATE TABLE IF NOT EXISTS public.wb_logs (
  id text PRIMARY KEY,
  log_date text,
  kind text,
  title text,
  body text,
  tags text,
  t bigint,
  up bigint
);

CREATE INDEX IF NOT EXISTS wb_tasks_date_idx ON public.wb_tasks (task_date);
CREATE INDEX IF NOT EXISTS wb_tasks_week_idx ON public.wb_tasks (week_no);
CREATE INDEX IF NOT EXISTS wb_permits_cat_idx ON public.wb_permits (category);
CREATE INDEX IF NOT EXISTS wb_logs_date_idx ON public.wb_logs (log_date);

GRANT USAGE ON SCHEMA public TO anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.wb_tasks TO anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.wb_permits TO anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.wb_milestones TO anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.wb_watchlist TO anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.wb_contacts TO anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.wb_logs TO anon, authenticated;
