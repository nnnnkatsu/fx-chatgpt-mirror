import { DurableObject } from "cloudflare:workers";

const VALID = /^\/(usdjpy|zarjpy|mxnjpy|gbpusd)(\/(analysis|1min|5min|15min|1h|4h|1day))?\/?$/;
const DAY = 86400000;
const result = (body, status = 200, headers = {}) => ({body: JSON.stringify(body), status, headers});
const responseOf = r => new Response(r.body, {status:r.status, headers:{"Content-Type":"application/json;charset=UTF-8", "Cache-Control":"no-store", "Access-Control-Allow-Origin":"*", ...r.headers}});
const coordinator = env => env.FX_COORDINATOR.getByName("shared-twelve-data-budget-v1");

// All callers and pairs share one persistent ledger. Failed calls still cost credits.
export class FxCoordinator extends DurableObject {
  constructor(ctx, env) { super(ctx, env); this.ctx=ctx; this.env=env; this.tail=Promise.resolve(); }
  run(path, kind="manual", event=null) {
    const job=this.tail.then(()=>this.execute(path,kind,event));
    this.tail=job.catch(()=>{}); return job;
  }
  async execute(path,kind,event) {
    const now=Date.now();
    if (!VALID.test(path)) return result({ok:false,error:"Invalid endpoint"},404);
    if (!this.env.TWELVE_DATA_API_KEY) return result({ok:false,error:"API key is not configured"},503);
    const key=path.toLowerCase().replace(/\/$/,"");
    let ledger=await this.ctx.storage.get("ledger");
    if (!ledger) {
      // Default is conservative: unknown usage before deployment is reserved for 24h.
      const seed=Number(this.env.FX_BOOTSTRAP_USED_CREDITS ?? 800);
      if (!Number.isInteger(seed)||seed<0||seed>800) return result({ok:false,error:"Invalid bootstrap usage"},503);
      ledger={events: seed ? [{at:now,cost:seed}] : [],seen:{}};
    }
    ledger.events=ledger.events.filter(e=>now-e.at<DAY);
    ledger.seen=Object.fromEntries(Object.entries(ledger.seen).filter(([,t])=>now-t<DAY));
    if (event && ledger.seen[event]) return result({ok:false,error:"Scheduled event already attempted"},409);
    if (event) { ledger.seen[event]=now; await this.ctx.storage.put("ledger",ledger); }
    const cached=await this.ctx.storage.get("cache:"+key);
    if (cached && now-cached.at>=0 && now-cached.at<60000) return cached.response;
    const cost=key.endsWith("/analysis")?7:1;
    const used=ledger.events.reduce((n,e)=>n+e.cost,0);
    const recent=ledger.events.filter(e=>now-e.at<75000).reduce((n,e)=>n+e.cost,0);
    const cap=kind==="scheduled"?600:800;
    if (used+cost>cap || recent+cost>8) {
      await this.ctx.storage.put("ledger",ledger);
      return result({ok:false,error:"Shared market quota reserved; retry later"},429,{"Retry-After":used+cost>cap?"3600":"75"});
    }
    ledger.events.push({at:now,cost});
    await this.ctx.storage.put("ledger",ledger); // reserve before starting any upstream request
    const response=await originalHandler.fetch(new Request("https://fx.internal"+key),this.env);
    const saved={body:await response.text(),status:response.status,headers:{}};
    if (response.ok) await this.ctx.storage.put("cache:"+key,{at:Date.now(),response:saved});
    return saved;
  }
}

export function scheduledPairs(ms) {
  const j=new Date(ms+9*3600000), day=j.getUTCDay(), h=j.getUTCHours(), m=j.getUTCMinutes();
  const weekday=day>=1 && day<=5;
  const previousWeekday=day>=2 && day<=6;
  if(weekday && m===4 && h>=8 && h<=23) return ["usdjpy"];
  if(m===14 && ((weekday && [8,12,16,20].includes(h)) || (h===0 && previousWeekday))) return ["mxnjpy"];
  if(m===39 && ((weekday && [8,12,16,20].includes(h)) || (h===0 && previousWeekday))) return ["zarjpy"];
  return [];
}

export default {
  async fetch(request,env) {
    const path=new URL(request.url).pathname.toLowerCase();
    if(path==="/") return originalHandler.fetch(request,env);
    if(!VALID.test(path)) return responseOf(result({ok:false,error:"Invalid endpoint"},404));
    if(request.method!=="GET") return responseOf(result({ok:false,error:"GET required"},405));
    if(!env.FX_COORDINATOR) return responseOf(result({ok:false,error:"FX_COORDINATOR binding required"},503));
    try { return responseOf(await coordinator(env).run(path,"manual",null)); }
    catch { return responseOf(result({ok:false,error:"Market coordinator unavailable"},503)); }
  },
  async scheduled(controller,env,ctx) {
    if(env.FX_SCHEDULE_ENABLED!=="true") return;
    // No delayed catch-up burst. UTC trigger times are converted to JST above.
    if(Date.now()-controller.scheduledTime>90000 || Date.now()<controller.scheduledTime) return;
    for(const pair of scheduledPairs(controller.scheduledTime)) {
      try {
        const r=await coordinator(env).run("/"+pair+"/analysis","scheduled",pair+":"+controller.scheduledTime);
        if(r.status!==200) { console.log(JSON.stringify({event:"prefetch_failed",pair,status:r.status})); continue; }
        const expected=JSON.parse(r.body).fetched_at_utc;
        // Existing Sakura endpoint captures this same cached result into its local file.
        // No GitHub token here; existing passive cron handles publishing.
        const relay=await fetch("https://drexworld.sakura.ne.jp/fx/"+pair+"/analysis",{signal:AbortSignal.timeout(20000),headers:{"Cache-Control":"no-cache"}});
        const payload=await relay.json();
        console.log(JSON.stringify({event:relay.ok&&payload.fetched_at_utc===expected?"sakura_cache_updated":"sakura_relay_failed",pair,status:relay.status,fetched_at_utc:expected}));
      } catch { console.log(JSON.stringify({event:"scheduled_refresh_failed"})); }
    }
  }
};

const originalHandler = {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = url.pathname.toLowerCase();

    const symbols = {
      usdjpy: "USD/JPY",
      zarjpy: "ZAR/JPY",
      mxnjpy: "MXN/JPY",
      gbpusd: "GBP/USD",
    };

    const intervals = {
      "1min": "1min",
      "5min": "5min",
      "15min": "15min",
      "1h": "1h",
      "4h": "4h",
      "1day": "1day",
    };

    if (path === "/") {
      return jsonResponse({
        service: "FX Real-Time & Technical Analysis API",
        source: "Twelve Data",
        examples: [
          "/usdjpy",
          "/usdjpy/15min",
          "/usdjpy/1h",
          "/usdjpy/4h",
          "/usdjpy/1day",
          "/usdjpy/analysis"
        ]
      });
    }

    const parts = path.split("/").filter(Boolean);

    if (parts.length < 1 || parts.length > 2) {
      return jsonResponse(
        { ok: false, error: "Invalid endpoint" },
        404
      );
    }

    const pairKey = parts[0];
    const symbol = symbols[pairKey];

    if (!symbol) {
      return jsonResponse(
        { ok: false, error: "Unsupported currency pair" },
        404
      );
    }

    if (!env.TWELVE_DATA_API_KEY) {
      return jsonResponse(
        { ok: false, error: "API key is not configured" },
        500
      );
    }

    try {
      // --------------------------------
      // 实时报价
      // --------------------------------
      if (parts.length === 1) {
        const price = await fetchPrice(symbol, env);

        return jsonResponse({
          ok: true,
          type: "price",
          symbol,
          price,
          fetched_at_utc: new Date().toISOString(),
          source: "Twelve Data"
        });
      }

      const endpoint = parts[1];

      // --------------------------------
      // 综合分析接口
      // --------------------------------
      if (endpoint === "analysis") {

        // ==================================================
        // 60秒 Cloudflare Cache
        // ==================================================

        const pricePromise = fetchPrice(symbol, env);

        const tfConfigs = {
          "1min": 80,
          "5min": 80,
          "15min": 80,
          "1h": 120,
          "4h": 120,
          "1day": 160
        };

        const promises = Object.entries(tfConfigs).map(
          async ([interval, outputsize]) => {

            const candles = await fetchCandles(
              symbol,
              interval,
              outputsize,
              env
            );

            return [
              interval,
              buildAnalysis(candles)
            ];
          }
        );

        const [price, results] = await Promise.all([pricePromise, Promise.all(promises)]);

        const analysis =
          Object.fromEntries(results);


        // ==================================================
        // 生成结果
        // ==================================================

        const response = new Response(
          JSON.stringify(
            {
              ok: true,
              type: "analysis",
              symbol,
              price,

              fetched_at_utc:
                new Date().toISOString(),

              cache_seconds: 60,

              source: "Twelve Data",

              analysis
            },
            null,
            2
          ),
          {
            status: 200,

            headers: {
              "Content-Type":
                "application/json;charset=UTF-8",

              // 浏览器不要自己长期缓存
              "Cache-Control":
                "public, max-age=0, s-maxage=60",

              "Access-Control-Allow-Origin":
                "*"
            }
          }
        );


        // ==================================================
        // 写入 Cloudflare Cache
        // 不等待写入完成，直接返回结果
        // ==================================================

        return response;
      }

      // --------------------------------
      // 普通 K线接口
      // --------------------------------
      const interval = intervals[endpoint];

      if (!interval) {
        return jsonResponse(
          {
            ok: false,
            error: "Unsupported endpoint",
            supported: [
              ...Object.keys(intervals),
              "analysis"
            ]
          },
          404
        );
      }

      const candles = await fetchCandles(
        symbol,
        interval,
        100,
        env
      );

      return jsonResponse({
        ok: true,
        type: "ohlc",
        symbol,
        interval,
        count: candles.length,
        fetched_at_utc: new Date().toISOString(),
        source: "Twelve Data",
        candles
      });

    } catch (error) {
      return jsonResponse(
        {
          ok: false,
          error: "Upstream market request failed"
        },
        500
      );
    }
  }
};


// ======================================================
// Twelve Data
// ======================================================

async function fetchPrice(symbol, env) {
  const apiUrl =
    "https://api.twelvedata.com/price" +
    "?symbol=" + encodeURIComponent(symbol) +
    "&apikey=" + encodeURIComponent(env.TWELVE_DATA_API_KEY);

  const response = await fetch(apiUrl, {
    signal: AbortSignal.timeout(10000),
    headers: { "Accept": "application/json" }
  });

  const data = await response.json();

  if (!response.ok || !data.price) {
    throw new Error(
      "Price API error: " + JSON.stringify(data)
    );
  }

  return Number(data.price);
}


// Daily date labels use the exchange timezone even when timezone=UTC is requested.
// Preserve the source date; normalize its local midnight as a date reference, not a tick time.
export function candleTimestamp(datetime, interval, exchangeTimezone) {
  if (interval !== "1day") return datetime.replace(" ", "T") + "Z";
  if (!/^\d{4}-\d{2}-\d{2}$/.test(datetime)) throw new Error("Invalid daily date");
  const zone = exchangeTimezone || "Australia/Sydney"; // documented Forex default
  const target = Date.parse(datetime + "T00:00:00Z");
  const fmt = new Intl.DateTimeFormat("en-GB", {timeZone:zone,year:"numeric",month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit",second:"2-digit",hourCycle:"h23"});
  let instant=target;
  for(let i=0;i<3;i++) {
    const v=Object.fromEntries(fmt.formatToParts(new Date(instant)).map(p=>[p.type,p.value]));
    const local=Date.UTC(Number(v.year),Number(v.month)-1,Number(v.day),Number(v.hour),Number(v.minute),Number(v.second));
    instant += target-local;
  }
  if (!Number.isFinite(instant)) throw new Error("Invalid daily timezone");
  return new Date(instant).toISOString();
}

async function fetchCandles(
  symbol,
  interval,
  outputsize,
  env
) {
  const apiUrl =
    "https://api.twelvedata.com/time_series" +
    "?symbol=" + encodeURIComponent(symbol) +
    "&interval=" + encodeURIComponent(interval) +
    "&outputsize=" + outputsize +
    "&timezone=UTC" +
    "&apikey=" + encodeURIComponent(env.TWELVE_DATA_API_KEY);

  const response = await fetch(apiUrl, {
    signal: AbortSignal.timeout(10000),
    headers: { "Accept": "application/json" }
  });

  const data = await response.json();

  if (!response.ok || !data.values) {
    throw new Error(
      "Time Series API error: " + JSON.stringify(data)
    );
  }

  // Twelve Data 默认最新在前
  // 这里反转为 时间从旧 -> 新
const candles = data.values
  .map(c => ({
    datetime: c.datetime,
    datetime_utc: candleTimestamp(c.datetime, interval, data.meta?.exchange_timezone),
    ...(interval === "1day" ? {source_timezone: data.meta?.exchange_timezone || "Australia/Sydney", timestamp_basis:"exchange_date_midnight", source_date:c.datetime} : {}),
    open: Number(c.open),
    high: Number(c.high),
    low: Number(c.low),
    close: Number(c.close)
  }))
  .filter(c => {
    const date = new Date(interval === "1day" ? c.datetime + "T00:00:00Z" : c.datetime_utc);
    const day = date.getUTCDay();

    // 过滤周六、周日
    return day !== 0 && day !== 6;
  })
  .reverse();
  candles.sourceTiming = sourceTiming(data, interval, candles);
  console.log(JSON.stringify({event:"source_candle_timing",symbol,...candles.sourceTiming}));
  return candles;
}

// Diagnostic only: do not change candle dates, freshness limits, or request count.
export function sourceTiming(data, requestedInterval, candles) {
  const allowed = ["1min","5min","15min","1h","4h","1day"];
  const date = v => typeof v === "string" && /^\d{4}-\d{2}-\d{2}(?: \d{2}:\d{2}:\d{2})?$/.test(v) ? v : null;
  const returnedInterval = allowed.includes(data.meta?.interval) ? data.meta.interval : null;
  let zone = null;
  try {
    const candidate = data.meta?.exchange_timezone;
    if (typeof candidate === "string" && /^[A-Za-z_]+(?:\/[A-Za-z_+-]+)*$/.test(candidate)) {
      new Intl.DateTimeFormat("en",{timeZone:candidate}); zone=candidate;
    }
  } catch {}
  const rawDates = data.values.slice(0,6).map(c=>date(c.datetime));
  const latest = candles.at(-1)?.datetime_utc || null;
  const checked = new Date().toISOString();
  const duration = {"1min":60,"5min":300,"15min":900,"1h":3600,"4h":14400,"1day":86400}[requestedInterval];
  return {
    requested_interval:requestedInterval,
    returned_interval:returnedInterval,
    interval_matches:returnedInterval === null ? null : returnedInterval === requestedInterval,
    exchange_timezone:zone,
    latest_raw_datetimes:rawDates,
    checked_at_utc:checked,
    latest_retained_at_utc:latest,
    candle_age_at_response_seconds:latest ? (Date.parse(checked)-Date.parse(latest))/1000 : null,
    current_gate_valid_until_utc:latest ? new Date(Date.parse(latest)+(duration+300)*1000).toISOString() : null,
    timestamp_basis:requestedInterval === "1day" ? "exchange_date_midnight" : "provider_intraday_utc",
    exact_session_open_verified:requestedInterval === "1day" ? false : null
  };
}


// ======================================================
// 技术分析
// ======================================================

function buildAnalysis(candles) {
  const closes = candles.map(c => c.close);

  const rsi = calculateRSI(closes, 14);
  const macd = calculateMACD(closes);
  const bb = calculateBollinger(closes, 20, 2);
  const atr = calculateATR(candles, 14);

  const latestCandles = candles.slice(-20);

  const recent20 = candles.slice(-20);

  const recentHigh = Math.max(
    ...recent20.map(c => c.high)
  );

  const recentLow = Math.min(
    ...recent20.map(c => c.low)
  );

  const currentCandle = candles[candles.length - 1];
  const previousClosedCandle = candles[candles.length - 2];

  const latestCandleTime = new Date(
    currentCandle.datetime_utc
  );

  const candleAgeSeconds = Math.max(
    0,
    Math.floor(
      (Date.now() - latestCandleTime.getTime()) / 1000
    )
  );

  return {
    source_timing: candles.sourceTiming,
    timezone: "UTC",

    latest_candle_at_utc:
      currentCandle.datetime_utc,

    candle_age_seconds: candleAgeSeconds,

    current_candle: currentCandle,
    previous_closed_candle: previousClosedCandle,

    indicators: {
      rsi14: round(rsi),

      macd: {
        macd: round(macd.macd),
        signal: round(macd.signal),
        histogram: round(macd.histogram)
      },

      bollinger20: {
        upper: round(bb.upper),
        middle: round(bb.middle),
        lower: round(bb.lower)
      },

      atr14: round(atr)
    },

    structure: {
      recent_20_high: round(recentHigh),
      recent_20_low: round(recentLow)
    },

    candles: latestCandles
  };
}


// ======================================================
// RSI
// ======================================================

function calculateRSI(values, period = 14) {
  if (values.length <= period) return null;

  let gains = 0;
  let losses = 0;

  for (let i = 1; i <= period; i++) {
    const diff = values[i] - values[i - 1];

    if (diff >= 0) {
      gains += diff;
    } else {
      losses -= diff;
    }
  }

  let avgGain = gains / period;
  let avgLoss = losses / period;

  for (let i = period + 1; i < values.length; i++) {
    const diff = values[i] - values[i - 1];

    const gain = diff > 0 ? diff : 0;
    const loss = diff < 0 ? -diff : 0;

    avgGain =
      ((avgGain * (period - 1)) + gain) /
      period;

    avgLoss =
      ((avgLoss * (period - 1)) + loss) /
      period;
  }

  if (avgLoss === 0) return 100;

  const rs = avgGain / avgLoss;

  return 100 - (100 / (1 + rs));
}


// ======================================================
// EMA / MACD
// ======================================================

function ema(values, period) {
  const multiplier = 2 / (period + 1);

  let value =
    values.slice(0, period)
      .reduce((a, b) => a + b, 0) /
    period;

  for (let i = period; i < values.length; i++) {
    value =
      (values[i] - value) *
      multiplier +
      value;
  }

  return value;
}


function calculateMACD(values) {
  if (values.length < 35) {
    return {
      macd: null,
      signal: null,
      histogram: null
    };
  }

  const macdSeries = [];

  for (let i = 26; i <= values.length; i++) {
    const slice = values.slice(0, i);

    const fast = ema(slice, 12);
    const slow = ema(slice, 26);

    macdSeries.push(fast - slow);
  }

  const macd =
    macdSeries[macdSeries.length - 1];

  const signal = ema(macdSeries, 9);

  return {
    macd,
    signal,
    histogram: macd - signal
  };
}


// ======================================================
// Bollinger Bands
// ======================================================

function calculateBollinger(
  values,
  period = 20,
  stdDev = 2
) {
  const slice = values.slice(-period);

  const middle =
    slice.reduce((a, b) => a + b, 0) /
    slice.length;

  const variance =
    slice.reduce(
      (sum, value) =>
        sum + Math.pow(value - middle, 2),
      0
    ) /
    slice.length;

  const sd = Math.sqrt(variance);

  return {
    upper: middle + sd * stdDev,
    middle,
    lower: middle - sd * stdDev
  };
}


// ======================================================
// ATR
// ======================================================

function calculateATR(candles, period = 14) {
  if (candles.length <= period) return null;

  const trs = [];

  for (let i = 1; i < candles.length; i++) {
    const current = candles[i];
    const previous = candles[i - 1];

    const tr = Math.max(
      current.high - current.low,
      Math.abs(
        current.high -
        previous.close
      ),
      Math.abs(
        current.low -
        previous.close
      )
    );

    trs.push(tr);
  }

  let atr =
    trs.slice(0, period)
      .reduce((a, b) => a + b, 0) /
    period;

  for (let i = period; i < trs.length; i++) {
    atr =
      ((atr * (period - 1)) + trs[i]) /
      period;
  }

  return atr;
}


// ======================================================
// 工具
// ======================================================

function round(value) {
  if (
    value === null ||
    value === undefined ||
    Number.isNaN(value)
  ) {
    return null;
  }

  return Number(value.toFixed(5));
}


function jsonResponse(data, status = 200) {
  return new Response(
    JSON.stringify(data, null, 2),
    {
      status,
      headers: {
        "Content-Type":
          "application/json;charset=UTF-8",

        "Cache-Control":
          "no-store, no-cache, must-revalidate",

        "Access-Control-Allow-Origin":
          "*"
      }
    }
  );
}