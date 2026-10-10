
/* ==========================================================================
   全景走势图（ECharts · 对数坐标 · 牛熊分区）
   ========================================================================== */
(function(){
  if (typeof echarts === 'undefined') { return; }
  const el = document.getElementById('chartAll');
  if (!el) return;

  const T = s => { const p = String(s).split('-').map(Number); return Date.UTC(p[0], p[1]-1, p[2]||1); };

  /* --- 牛熊分区（1=牛 0=熊） --- */
  const ZONES = [
    ['1990-12-19','1992-05-26',1],['1992-05-26','1992-11-17',0],
    ['1992-11-17','1993-02-16',1],['1993-02-16','1994-07-29',0],
    ['1994-07-29','1994-09-13',1],['1994-09-13','1996-01-19',0],
    ['1996-01-19','1997-05-12',1],['1997-05-12','1999-05-17',0],
    ['1999-05-17','2001-06-14',1],['2001-06-14','2005-06-06',0],
    ['2005-06-06','2007-10-16',1],['2007-10-16','2008-10-28',0],
    ['2008-10-28','2009-08-04',1],['2009-08-04','2013-06-25',0],
    ['2013-06-25','2015-06-12',1],['2015-06-12','2016-01-27',0],
    ['2016-01-27','2018-01-24',1],['2018-01-24','2019-01-04',0],
    ['2019-01-04','2021-02-18',1],['2021-02-18','2022-04-27',0],
    ['2022-04-27','2022-07-05',1],['2022-07-05','2022-10-31',0],
    ['2022-10-31','2023-05-09',1],['2023-05-09','2024-02-05',0],
    ['2024-02-05','2024-05-20',1],['2024-05-20','2024-09-18',0],
    ['2024-09-18','2025-11-14',1],['2025-11-14','2026-07-20',0],
    ['2026-07-20','2026-09-29',1]
  ];

  /* --- 区间极值（用月线序列实际点位，避免标签与曲线错位） --- */
  function ext(y1,m1,y2,m2,mode){
    const t1 = Date.UTC(y1,m1-1,1), t2 = Date.UTC(y2,m2-1,1);
    let best = null;
    for (let i=0;i<SERIES.length;i++){
      const d = SERIES[i];
      if (d[0] < t1 || d[0] > t2) continue;
      if (!best || (mode==='max' ? d[1] > best[1] : d[1] < best[1])) best = d;
    }
    return best;
  }
  /* 标签数字为该轮周期的历史极值（部分为盘中价，如 2007 年 6124.04、2015 年 5178.19），
     坐标锚点取自月线序列的实际极值点，两者在对数坐标下视觉偏差可忽略，详见页脚口径说明。 */
  const PEAKS = [
    [ext(1990,12,1992,9,'max'),  '1992 顶 1429'],
    [ext(2000,1,2002,6,'max'),   '2001 顶 2245'],
    [ext(2007,6,2008,3,'max'),   '2007 顶 6124 · 历史最高'],
    [ext(2015,1,2016,6,'max'),   '2015 顶 5178'],
    [ext(2020,6,2021,6,'max'),   '2021 顶 3731'],
    [ext(2025,10,2026,6,'max'),  '2026 顶 4258']
  ].filter(x=>x[0]);
  const TROUGHS = [
    [ext(1993,6,1995,6,'min'),   '1994 底 325'],
    [ext(2004,6,2005,12,'min'),  '2005 底 998'],
    [ext(2012,6,2013,12,'min'),  '2013 底 1849'],
    [ext(2018,9,2019,6,'min'),   '2019 底 2440'],
    [ext(2023,10,2024,6,'min'),  '2024 底 2635'],
    [ext(2026,6,2026,9,'min'),   '2026 底 3741']
  ].filter(x=>x[0]);

  const chart = echarts.init(el, null, {renderer:'canvas'});

  const option = {
    backgroundColor: 'transparent',
    animationDuration: 1600,
    animationEasing: 'cubicOut',
    grid: {left: 66, right: 28, top: 46, bottom: 46},
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(33,23,23,.96)',
      borderColor: '#c9a227',
      borderWidth: 1,
      textStyle: {color:'#f5f0ef', fontSize:12.5},
      axisPointer: {type:'line', lineStyle:{color:'#c9a227', type:'dashed'}},
      formatter: function(ps){
        const p = ps[0];
        const d = new Date(p.value[0]);
        const y = d.getUTCFullYear(), m = d.getUTCMonth()+1;
        return `<b style="color:#e8c96a">${y} 年 ${m} 月</b><br/>`
             + `上证综指（月收盘）：<b style="color:#f2454f">${Number(p.value[1]).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2})}</b> 点`;
      }
    },
    xAxis: {
      type: 'time',
      axisLine: {lineStyle:{color:'#4a3639'}},
      axisTick: {lineStyle:{color:'#4a3639'}},
      axisLabel: {
        color:'#948887', fontSize: 11.5,
        formatter: function(v){ return new Date(v).getUTCFullYear() + ''; }
      },
      splitLine: {show:false}
    },
    yAxis: {
      type: 'log',
      logBase: 10,
      min: 90,
      max: 7200,
      axisLine: {show:false},
      axisTick: {show:false},
      axisLabel: {
        color:'#948887', fontSize: 11.5,
        formatter: function(v){ return String(Math.round(v)); }
      },
      splitLine: {lineStyle:{color:'rgba(74,54,57,.42)', type:'dashed'}}
    },
    series: [{
      name: '上证综指',
      type: 'line',
      data: SERIES,
      showSymbol: false,
      symbolSize: 3,
      smooth: false,
      sampling: 'lttb',
      lineStyle: {width: 2, color: '#f2454f', shadowColor:'rgba(242,69,79,.5)', shadowBlur:12},
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0,0,0,1,[
          {offset:0, color:'rgba(208,32,47,.34)'},
          {offset:.55, color:'rgba(208,32,47,.10)'},
          {offset:1, color:'rgba(208,32,47,.01)'}
        ])
      },
      markArea: {
        silent: true,
        data: ZONES.map(z=>{
          const bull = z[2] === 1;
          return [
            {xAxis: T(z[0]), itemStyle:{color: bull ? 'rgba(208,32,47,.085)' : 'rgba(18,160,106,.095)'}},
            {xAxis: T(z[1])}
          ];
        })
      },
      markPoint: {
        symbol: 'circle',
        symbolSize: 8,
        itemStyle: {color:'#c9a227', borderColor:'#0c0909', borderWidth:2},
        label: {
          formatter: '{b}',
          color:'#e8c96a', fontSize: 11, fontWeight: 700,
          backgroundColor:'rgba(12,9,9,.85)', padding:[3,6], borderRadius:4,
          borderColor:'rgba(201,162,39,.5)', borderWidth:1
        },
        data: PEAKS.map(p=>({
          name: p[1], coord: p[0], value: p[0][1],
          label: {position:'top'}
        })).concat(TROUGHS.map(p=>({
          name: p[1], coord: p[0], value: p[0][1],
          itemStyle:{color:'#2fc98c', borderColor:'#0c0909', borderWidth:2},
          label:{
            formatter:'{b}', position:'bottom', color:'#2fc98c',
            backgroundColor:'rgba(12,9,9,.85)', padding:[3,6], borderRadius:4,
            borderColor:'rgba(47,201,140,.5)', borderWidth:1, fontSize:11, fontWeight:700
          }
        })))
      },
      markLine: {
        silent: true, symbol:'none',
        lineStyle: {color:'rgba(201,162,39,.42)', type:'dashed', width:1},
        label: {color:'#c9a227', fontSize:11, formatter:'{b}', position:'insideStartTop'},
        data: [
          {yAxis: 1000, name:'1000 点'},
          {yAxis: 3000, name:'3000 点'},
          {yAxis: 6124.04, name:'历史最高 6124.04'}
        ]
      }
    }]
  };

  chart.setOption(option);
  addEventListener('resize', ()=>chart.resize());
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(()=>chart.resize());
})();
