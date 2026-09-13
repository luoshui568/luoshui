CREATE TABLE IF NOT EXISTS public.wb_works (
  id          text PRIMARY KEY,
  horizon     text NOT NULL DEFAULT '本周',
  title       text NOT NULL DEFAULT '',
  detail      text DEFAULT '',
  category    text DEFAULT '战略',
  priority    text DEFAULT 'P1',
  status      text DEFAULT 'todo',
  progress    integer DEFAULT 0,
  owner       text DEFAULT '',
  start_date  text DEFAULT '',
  due_date    text DEFAULT '',
  kpi         text DEFAULT '',
  metric      text DEFAULT '',
  baseline    text DEFAULT '',
  target      text DEFAULT '',
  key_actions text DEFAULT '',
  resources   text DEFAULT '',
  risk        text DEFAULT '',
  parent_id   text DEFAULT '',
  milestone   text DEFAULT '',
  review_date text DEFAULT '',
  note        text DEFAULT '',
  tags        text DEFAULT '',
  sort        integer DEFAULT 99,
  t           bigint,
  up          bigint
);

CREATE INDEX IF NOT EXISTS wb_works_horizon_idx ON public.wb_works (horizon);
CREATE INDEX IF NOT EXISTS wb_works_sort_idx    ON public.wb_works (sort);
CREATE INDEX IF NOT EXISTS wb_works_due_idx     ON public.wb_works (due_date);

ALTER TABLE public.wb_works ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS wb_works_anon_all ON public.wb_works;
CREATE POLICY wb_works_anon_all ON public.wb_works FOR ALL TO anon, authenticated USING (true) WITH CHECK (true);

GRANT USAGE ON SCHEMA public TO anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.wb_works TO anon, authenticated;
