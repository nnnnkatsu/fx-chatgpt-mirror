# FX → GitHub → ChatGPT：ZARJPY 只读镜像

只增加镜像，不改变 Twelve Data → Cloudflare → Sakura v3.1 的 API、launcher、PATH nonce 或其他货币。
当前 data/zarjpy.json 是从现有 Sakura fresh analysis 取得的真实单次快照，**未在 Sakura 部署自动同步**。
文件可随时间过期；上传成功、HTTP 200 或能看到价格不等于实时可用。

## 固定 RAW URL

https://raw.githubusercontent.com/nnnnkatsu/fx-chatgpt-mirror/main/data/zarjpy.json

- data/zarjpy.json：唯一正式镜像路径。
- mirror.py：读取现有 analysis 文件，校验后通过 GitHub Contents API 推送同一份行情。
- DEPLOYMENT.md：Sakura 最小接入、令牌配置、重试和验收。
- tests/test_mirror.py：离线保真、时间、安全拒绝与冲突重试测试。
- 根目录 zarjpy.json：旧版不可交易示例，仅为保留旧链接；不再更新，不用于监测。
- examples/export.example.json：旧版输入格式示例，已不供新版脚本使用。

## 原数据保留原则

真实接口为：
`ok / type / symbol / price / fetched_at_utc / cache_seconds / source / analysis`。
analysis 原来就包含六个周期：1min、5min、15min、1h、4h、1day。
各周期包含 timezone、latest_candle_at_utc、candle_age_seconds、current_candle、
previous_closed_candle、indicators、structure、candles。全部保留，不重算技术指标。

源 source="Twelve Data"，不会改写为 Sakura。Sakura 是传输路径而非行情供应商。
仅在缺失时补 pair="ZARJPY"、generated_at_utc=null；
新增 _mirror 保存传输来源、包装时间、原对象 SHA256 和 mode=snapshot。
如果源以后提供 generated_at_utc，则原样保留。不存在的生成时间不能用 fetched 或上传时间冒充。
SHA256 针对排序、紧凑序列化后的原 JSON 对象，是保真检查值，不是来源签名。
保留 JSON 字段和值；不保证空白、键顺序、数字文字格式逐字节相同。

实际日线时间为 YYYY-MM-DDZ。它不是完整 ISO 时间；保留原值，校验时在源 timezone=UTC 条件下
按该日期 00:00 UTC 解析，仅用于与源 candle_age 一致的年龄检查，不声称它是实际交易日开盘瞬间。
current_candle 可能仍形成中，不自动视为收盘确认；收盘条件优先使用 previous_closed_candle。

## 新鲜度：每次读取重新计算

1. ok=true、type=analysis、symbol=ZAR/JPY、pair=ZARJPY、source=Twelve Data；
   price 为正数，六周期和指标完整，否则拒绝。
2. now - fetched_at_utc 必须在 0–300 秒。未来时间拒绝。
3. generated_at_utc 若有值：必须不早于 fetched、不晚于当前时刻，年龄≤300秒。
   当前源没有该字段，因此 null 明确表示无法独立验证生成时间；
   本阶段依据 fetched + 各周期蜡烛时间交叉校验，不把 null 解释为“刚生成”。
   若某任务强制要求独立生成时间，该任务应拒绝此快照，直到源能提供真实值。
4. analysis[周期].latest_candle_at_utc 必须与 current_candle.datetime_utc 一致。
   读取时重算年龄：1min≤360秒、5min≤600秒、15min≤1200秒、
   H1≤3900秒、H4≤14700秒、D1≤86700秒；均不得为负。
5. 原 candle_age_seconds 是生成响应时的值，不会随着 GitHub 缓存自动增长。
   必须与 fetched - latest 的差值在60秒内，并使用读取时重新计算的年龄判过期。
6. 周末或源停止更新也不重写时间来“保鲜”。先判断市场状态，再决定报休市或读取失败。
7. _mirror.mirrored_at_utc 只表示包装时刻，不能替代任何行情时间戳。
   fetched 的精确上游语义目前由公开接口提供；未审阅 Worker/Sakura 源码，故不能证明所有周期都在该时刻重新向 Twelve Data 拉取。
   蜡烛交叉检查能发现明显旧数据，但不能证明形成中蜡烛的每一个价格都最新。

## 普通 ChatGPT 测试用规则

先尝试 Sakura v3.1 launcher（保持原 PATH nonce 流程）。
仅当网页读取层拒绝或无法取得可用数据时，打开上述 RAW 链接。
按本 README 验证 freshness，合格才进行 ZARJPY D1/H4/H1 分析；
两个来源都无法读取或镜像过期，输出【实时读取失败】。
普通 web reader 是否可稳定读取要独立实测，不能由本机 HTTP 200 推断。

本次不修改现有定时任务，不扩展其他三个货币。
交易背景仅为用户提供的记录：2026-09-24 已全部止损，FLAT，后续是 NEW FIRST TRANCHE，
不是加仓。Carry/宏观及任何入场条件仍需分析时重新核实；此项目不产生交易指令。

## 本地验证

```sh
python3 -m unittest discover -s tests -v
python3 mirror.py /private/path/zarjpy-analysis.json --public-export-reviewed --output /private/path/preview.json
```

不要公开 private/、环境文件、服务器配置或任何密钥。
