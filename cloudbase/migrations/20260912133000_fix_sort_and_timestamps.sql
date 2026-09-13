ALTER TABLE public.wb_contacts ADD COLUMN IF NOT EXISTS sort integer;
UPDATE public.wb_contacts c SET sort = v.s FROM (VALUES (1,'券商矿业分析师'),(2,'地质勘查院/地矿局专家'),(3,'矿业专业律师'),(4,'跨境税务师'),(5,'银行并购部/授信经理'),(6,'中信保项目险经理'),(7,'已出海矿企中层'),(8,'矿山运营负责人'),(9,'下游采购/技术负责人')) AS v(s, rn) WHERE c.role_name = v.rn;
UPDATE public.wb_tasks SET t = COALESCE(t, 1789220065547), up = COALESCE(up, 1789220065547);
UPDATE public.wb_permits SET t = COALESCE(t, 1789220065547), up = COALESCE(up, 1789220065547);
UPDATE public.wb_milestones SET t = COALESCE(t, 1789220065547), up = COALESCE(up, 1789220065547);
UPDATE public.wb_watchlist SET t = COALESCE(t, 1789220065547), up = COALESCE(up, 1789220065547);
UPDATE public.wb_contacts SET t = COALESCE(t, 1789220065547), up = COALESCE(up, 1789220065547);
UPDATE public.wb_logs SET t = COALESCE(t, 1789220065547), up = COALESCE(up, 1789220065547);
CREATE INDEX IF NOT EXISTS wb_contacts_sort_idx ON public.wb_contacts (sort);
