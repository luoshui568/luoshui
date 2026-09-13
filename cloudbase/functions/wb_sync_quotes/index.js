/**
 * 投资标的 · 行情 + 基本面 同步云函数
 *
 * 由定时触发器在【每个交易日 15:35】调用（cron: 0 35 15 * * 1-5 *）。
 *
 * 数据来源与字段：
 *   ① 腾讯行情 qt.gtimg.cn（GBK，单批 55 只）
 *        涨幅 / 现价 / 总金额 / 市盈(动) / 市盈(TTM) / 市净率 / 股息率 / 总市值 / 区间涨幅
 *   ② 东财 push2delay 行业板块列表（5 页 × 100 个板块）
 *        每个板块的市盈率 → 「行业PE」
 *   ③ 东财 datacenter RPT_F10_BASIC_ORGINFO
 *        EM2016（有色金属-稀有金属-钼 这种三级分类）→ 「细分行业」
 *        PROVINCE → 「地区」
 *   ④ 东财 datacenter RPT_DMSK_FN_BALANCE（最新报告期）
 *        TOTAL_ASSETS → 「总资产(亿)」；INDUSTRY_CODE → 板块代码（PE 兜底匹配）
 *   ⑤ 净资产 = 总市值 ÷ 市净率（PB 反推归母权益）
 *
 * 「行业PE」取值优先级：细分行业名精确命中东财板块 → 用该板块 PE；
 *                      否则用个股所属行业板块（BKxxxx）的 PE。
 *
 * 数据源可达性（2026-09-13 在本机与云函数内实测）：
 *   ✅ qt.gtimg.cn                    CORS *
 *   ✅ push2delay.eastmoney.com        CORS *（push2 主域连不通，用这个）
 *   ✅ datacenter-web.eastmoney.com    无 CORS，只能服务端调
 *
 * 字段保护：wb_stocks.lock_fields 里登记过的字段一律不写（用户手工改过）。
 * 节流：细分行业 / 地区 30 天刷一次；总资产只在缺失时拉（财报季度更新）。
 *
 * 环境变量：ENV_ID（CloudBase 环境 ID）、RDB_KEY（可发布密钥）
 */
const ENV_ID = process.env.ENV_ID || '';
const RDB_KEY = process.env.RDB_KEY || '';
const REST = ENV_ID ? ('https://' + ENV_ID + '.api.tcloudbasegateway.com/v1/rdb/rest/') : '';
const QT_BATCH = 55;

const EB_DELAY = 'https://push2delay.eastmoney.com/api/qt/';
const EB_DC = 'https://datacenter-web.eastmoney.com/api/data/v1/get';
const EB_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
            + '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36';
const EB_CHUNK = 30;                            /* datacenter in(...) 每批代码数 */
const META_STALE_MS = 30 * 24 * 3600 * 1000;    /* 行业 / 地区 30 天刷新一次 */

/* 腾讯行情 88 字段的索引（与前端 QI 保持一致） */
const QI = {
  name: 1, code: 2, price: 3, quote_time: 30, chg_pct: 32,
  amount_wan: 37, pe_ttm: 39, mkt_cap_yi: 45, pb: 46, pe_fwd: 52,
  chg_ytd: 62, div_yield: 64, chg_10d: 69, chg_20d: 70, chg_60d: 71
};

function txPrefix(code) {
  const c = String(code == null ? '' : code).replace(/[^0-9]/g, '');
  if (/^(6|9|5)/.test(c)) return 'sh';
  if (/^(4|8)/.test(c)) return 'bj';
  return 'sz';
}
function num(v) { const x = parseFloat(v); return isNaN(x) ? null : x; }
function isLocked(row, field) {
  const lf = String((row && row.lock_fields) || '');
  return lf.split(',').map(s => s.trim()).indexOf(field) >= 0;
}
function chunks(arr, n) {
  const out = [];
  for (let i = 0; i < arr.length; i += n) out.push(arr.slice(i, i + n));
  return out;
}

/* ---------------- RDB ---------------- */
async function rdbGet(path) {
  const r = await fetch(REST + path, { headers: { Authorization: 'Bearer ' + RDB_KEY } });
  if (!r.ok) throw new Error('GET ' + path + ' -> ' + r.status + ' ' + (await r.text()).slice(0, 200));
  return r.json();
}
async function rdbUpsert(rows) {
  if (!rows.length) return true;
  const r = await fetch(REST + 'wb_stocks?on_conflict=code', {
    method: 'POST',
    headers: {
      Authorization: 'Bearer ' + RDB_KEY,
      'Content-Type': 'application/json',
      Prefer: 'resolution=merge-duplicates,return=minimal'
    },
    body: JSON.stringify(rows)
  });
  if (!r.ok) throw new Error('UPSERT -> ' + r.status + ' ' + (await r.text()).slice(0, 300));
  return true;
}

/* ---------------- 通用 ---------------- */
async function ebJson(url) {
  const r = await fetch(url, { headers: { 'User-Agent': EB_UA, Accept: '*/*' } });
  if (!r.ok) throw new Error('EB ' + r.status + ' ' + url.slice(0, 90));
  return r.json();
}
/* datacenter 通用查询：按代码批 in(...) */
async function dcQuery(reportName, columns, codes, extraFilter, sortCol, pageSize, src, client) {
  const out = [];
  for (const chunk of chunks(codes, EB_CHUNK)) {
    let filter = '(SECURITY_CODE in ("' + chunk.join('","') + '"))';
    if (extraFilter) filter += extraFilter;
    const url = EB_DC + '?reportName=' + reportName
      + '&columns=' + columns
      + '&filter=' + encodeURIComponent(filter)
      + '&pageNumber=1&pageSize=' + (pageSize || 600)
      + (sortCol ? '&sortColumns=' + sortCol + '&sortTypes=-1' : '')
      + '&source=' + (src || 'WEB') + '&client=' + (client || 'WEB');
    try {
      const d = (await ebJson(url)).result || {};
      out.push(...(d.data || []));
    } catch (e) { /* 单批失败不影响其它批 */ }
    await new Promise(r => setTimeout(r, 150));
  }
  return out;
}

/* ---------------- ① 腾讯行情 ---------------- */
async function fetchQuotes(codes) {
  const out = [];
  for (let i = 0; i < codes.length; i += QT_BATCH) {
    const chunk = codes.slice(i, i + QT_BATCH);
    const url = 'https://qt.gtimg.cn/q=' + chunk.map(c => txPrefix(c) + c).join(',');
    const r = await fetch(url, { headers: { 'User-Agent': 'Mozilla/5.0' } });
    const txt = new TextDecoder('gbk').decode(await r.arrayBuffer());
    txt.split('\n').forEach(line => {
      const k = line.indexOf('="');
      if (k < 0) return;
      const v = line.slice(k + 2).replace(/";?\s*$/, '').split('~');
      if (v.length < 45 || !v[QI.name]) return;
      const code = v[QI.code];
      const qt = v[QI.quote_time] || '';
      const aw = num(v[QI.amount_wan]), my = num(v[QI.mkt_cap_yi]);
      out.push({
        id: 'st_' + code,
        code: code,
        exchange: txPrefix(code),
        name: v[QI.name],
        chg_pct: num(v[QI.chg_pct]),
        price: num(v[QI.price]),
        amount: aw === null ? null : Math.round(aw * 1e4),
        mkt_cap: my === null ? null : Math.round(my * 1e8),
        pe_fwd: num(v[QI.pe_fwd]),
        pe_ttm: num(v[QI.pe_ttm]),
        pb: num(v[QI.pb]),
        div_yield: num(v[QI.div_yield]),
        chg_ytd: num(v[QI.chg_ytd]),
        chg_10d: num(v[QI.chg_10d]),
        chg_20d: num(v[QI.chg_20d]),
        chg_60d: num(v[QI.chg_60d]),
        quote_time: qt,
        quote_date: qt.length >= 8 ? (qt.slice(0, 4) + '-' + qt.slice(4, 6) + '-' + qt.slice(6, 8)) : '',
        up: Date.now()
      });
    });
    if (i + QT_BATCH < codes.length) await new Promise(r => setTimeout(r, 200));
  }
  return out;
}

/* ---------------- ② 行业板块市盈率表 ---------------- */
async function fetchBoardPE() {
  const map = {};
  for (let pn = 1; pn <= 6; pn++) {
    const url = EB_DELAY + 'clist/get?po=1&np=1&fltt=2&invt=2&fid=f3'
      + '&pn=' + pn + '&pz=100&fs=m:90+t:2+f:!50&fields=f12,f14,f9';
    let d;
    try { d = (await ebJson(url)).data || {}; } catch (e) { break; }
    const diff = d.diff || [];
    diff.forEach(x => { if (x && x.f12) map[x.f12] = { name: x.f14, pe: num(x.f9) }; });
    if (diff.length < 100) break;
    await new Promise(r => setTimeout(r, 150));
  }
  return map;
}
function peByName(boardMap, name) {
  if (!name) return null;
  const hit = Object.keys(boardMap).filter(k => boardMap[k].name === name)[0];
  return hit ? boardMap[hit].pe : null;
}

/* ---------------- ③ 细分行业 / 地区（东财公司概况） ---------------- */
async function fetchOrgInfo(codes) {
  const rows = await dcQuery('RPT_F10_BASIC_ORGINFO',
    'SECURITY_CODE,SECURITY_NAME_ABBR,EM2016,PROVINCE', codes, '', '', 200, 'HSF10', 'PC');
  const out = {};
  rows.forEach(x => {
    const c = String(x.SECURITY_CODE || '');
    if (!c) return;
    /* EM2016 形如「有色金属-稀有金属-钼」，取最后一段做细分行业（最细粒度） */
    const seg = String(x.EM2016 || '').split('-');
    out[c] = {
      sub_industry: (seg[seg.length - 1] || '').trim(),
      full_industry: String(x.EM2016 || '').trim(),
      region: String(x.PROVINCE || '').trim()
    };
  });
  return out;
}

/* ---------------- ④ 总资产 + 所属行业板块 ---------------- */
async function fetchBalance(codes) {
  const rows = await dcQuery('RPT_DMSK_FN_BALANCE',
    'SECURITY_CODE,TOTAL_ASSETS,INDUSTRY_CODE,INDUSTRY_NAME,REPORT_DATE',
    codes, "(REPORT_DATE>='2024-12-31')", 'REPORT_DATE', 900);
  const out = {};
  rows.forEach(x => {                      /* 已按报告期倒序，首次出现即最新 */
    const c = String(x.SECURITY_CODE || '');
    if (!c || out[c]) return;
    const ta = num(x.TOTAL_ASSETS);
    out[c] = {
      total_assets: ta === null ? null : +(ta / 1e8).toFixed(2),
      board: x.INDUSTRY_CODE ? ('BK' + x.INDUSTRY_CODE) : '',
      board_name: String(x.INDUSTRY_NAME || '').trim()
    };
  });
  return out;
}

/* ---------------- main ---------------- */
exports.main = async () => {
  if (!REST || !RDB_KEY) return { ok: false, msg: '缺少 ENV_ID / RDB_KEY 环境变量' };

  const list = await rdbGet('wb_stocks?select=code,lock_fields,sub_industry,region,'
    + 'total_assets,info_at&limit=2000');
  const rows0 = (list || []).filter(x => /^\d{6}$/.test(String(x.code || '')));
  if (!rows0.length) return { ok: true, total: 0, msg: '标的池为空，跳过' };

  const codes = rows0.map(x => String(x.code));
  const err = { quotes: '', boards: '', org: '', balance: '' };
  const stat = { quotes: 0, boards: 0, org: 0, balance: 0 };

  /* ① 行情 */
  const qMap = {};
  try {
    const qs = await fetchQuotes(codes);
    qs.forEach(r => { qMap[r.code] = r; });
    stat.quotes = Object.keys(qMap).length;
  } catch (e) { err.quotes = String(e.message || e).slice(0, 120); }

  /* ② 板块 PE（每日刷新，5 个请求） */
  let boardMap = {};
  try {
    boardMap = await fetchBoardPE();
    stat.boards = Object.keys(boardMap).length;
  } catch (e) { err.boards = String(e.message || e).slice(0, 120); }

  /* ③ 细分行业 / 地区：缺失或超 30 天才拉 */
  const orgNeed = rows0.filter(x => {
    if (!x.sub_industry || !x.region) return true;
    if (!x.info_at) return true;
    return (Date.now() - Date.parse(x.info_at)) > META_STALE_MS;
  }).map(x => String(x.code));
  let orgMap = {};
  if (orgNeed.length) {
    try { orgMap = await fetchOrgInfo(orgNeed); stat.org = Object.keys(orgMap).length; }
    catch (e) { err.org = String(e.message || e).slice(0, 120); }
  }

  /* ④ 总资产：只在缺失时拉 */
  const balNeed = rows0.filter(x => x.total_assets === null || x.total_assets === undefined)
    .map(x => String(x.code));
  let balMap = {};
  if (balNeed.length) {
    try { balMap = await fetchBalance(balNeed); stat.balance = Object.keys(balMap).length; }
    catch (e) { err.balance = String(e.message || e).slice(0, 120); }
  }

  /* 合并 */
  const merged = [];
  rows0.forEach(src => {
    const code = String(src.code);
    const q = qMap[code], o = orgMap[code], b = balMap[code];
    const row = Object.assign({},
      q || { id: 'st_' + code, code: code, exchange: txPrefix(code) });
    row.up = Date.now();

    /* 净资产：PB 反推 —— 总市值(元)/PB = 归母权益(元) */
    if (q && q.mkt_cap && q.pb > 0 && !isLocked(src, 'net_assets')) {
      row.net_assets = +((q.mkt_cap / 1e8 / q.pb).toFixed(2));
    }

    /* 细分行业 / 地区 */
    const sub = (o && o.sub_industry) || (b && b.board_name) || '';
    if (sub && !isLocked(src, 'sub_industry')) row.sub_industry = sub;
    if (o && o.region && !isLocked(src, 'region')) row.region = o.region;

    /* 行业PE：细分行业名精确命中板块 → 用该板块；否则用个股所属行业板块 */
    let pe = null;
    if (sub) pe = peByName(boardMap, sub);
    if (pe === null && b && b.board_name) pe = peByName(boardMap, b.board_name);
    if (pe === null && b && b.board) pe = (boardMap[b.board] || {}).pe;
    if (pe === null || pe === undefined) {
      const bd = Object.keys(boardMap).filter(k => boardMap[k].name === sub)[0];
      if (bd) pe = boardMap[bd].pe;
    }
    if (pe !== null && pe !== undefined && !isLocked(src, 'ind_pe')) row.ind_pe = pe;

    if (o && !isLocked(src, 'info_at')) row.info_at = new Date().toISOString();

    /* 总资产 */
    if (b && b.total_assets !== null && !isLocked(src, 'total_assets')) {
      row.total_assets = b.total_assets;
    }
    merged.push(row);
  });

  await rdbUpsert(merged);
  return {
    ok: true, total: codes.length, updated: merged.length,
    stat: stat,
    need: { org: orgNeed.length, balance: balNeed.length },
    err: err,
    at: new Date().toISOString()
  };
};
