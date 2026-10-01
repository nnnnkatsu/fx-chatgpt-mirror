# FX → Sakura → GitHub 只读行情镜像

当前支持 USDJPY、ZARJPY、MXNJPY。保留现有 Twelve Data → Cloudflare Worker → Sakura v3.1 API、launcher和PATH nonce；GitHub只是已有行情的只读镜像。

## 当前使用方式（2026-10-01）

- **临时查询新行情：[浏览器手动触发正式流程](MANUAL-REFRESH.md)**。打开新的launcher，点击对应fresh analysis一次，再让ChatGPT读取镜像。没有新增刷新接口。
- **定时检查：[当前JST时表](cloudflare/SCHEDULE-2026-09-30.md)**。Worker按既定时点预取，仍共用800 credits/日和8 credits/分钟额度控制；不为镜像新增采集。
- **同步：[新缓存立即发布，120秒Cron补偿](EVENT-SYNC.md)**。源未改变不重复提交。GitHub读取不触发刷新。
- **诊断：**Sakura保存私有运行日志；ChatGPT任务结果末尾保存读取端JSON诊断。当前GitHub连接器写入测试返回403，不假定任务能自动把日志写入本仓库。

## 正式行情文件

| 货币 | 文件 |
| --- | --- |
| USDJPY | [data/usdjpy.json](https://raw.githubusercontent.com/nnnnkatsu/fx-chatgpt-mirror/main/data/usdjpy.json) |
| ZARJPY | [data/zarjpy.json](https://raw.githubusercontent.com/nnnnkatsu/fx-chatgpt-mirror/main/data/zarjpy.json) |
| MXNJPY | [data/mxnjpy.json](https://raw.githubusercontent.com/nnnnkatsu/fx-chatgpt-mirror/main/data/mxnjpy.json) |

GBPUSD没有配置镜像。根目录zarjpy.json及examples目录是旧示例，不能用于实时交易。

## 数据和新鲜度

保留原analysis六周期、指标、结构与蜡烛数据，不重算指标。源source仍为Twelve Data；generated_at_utc源未提供时为null。_mirror记录复制元数据，不冒充源生成时间。

每次以真实读取时间重新验证，并在给出新交易计划前复核：

1. ok=true、type=analysis、货币一致、source=Twelve Data、price为正数。
2. fetched_at_utc距实际当前UTC为0–300秒，未来时间拒绝。
3. 校验generated_at_utc（若有）；缺失不补造。mirrored_at_utc只是镜像构建时间，不能替代源时间或上传完成时间。
4. 六周期latest_candle_at_utc与current_candle.datetime_utc一致。读取时K线年龄上限：1min 360秒、5min 600秒、15min 1200秒、1h 3900秒、4h 14700秒、1day 86700秒。
5. 源candle_age_seconds是快照生成时的年龄，不会自动增长；与fetched减latest的差允许60秒组装容差，但最终新鲜度必须按实际读取时间重算。
6. 日线现使用显式UTC时间，并保留source_date/source_timezone及exchange_date_midnight说明；不能把交易所当地日期直接补Z当UTC午夜。current_candle不自动代表收盘确认。
7. 超过60秒的快照不作为此刻精确可成交报价。HTTP200、最新提交或镜像上传成功都不能替代上述校验。市场关闭时不新增行情请求。

main版本陈旧或不明确时，通过GitHub连接器查询当前文件在main上的最新commit，再按本次返回的完整SHA读取；blob SHA不是commit SHA，历史验收SHA不能复用为实时结果。

## 安全与运行

不提交API key、GitHub token、Sakura密码或私有配置。GitHub凭据仅位于Sakura私有目录/既有Cron环境；具体权限和回滚说明见[事件同步说明](EVENT-SYNC.md)。mirror.py/cache_sync.py执行源验证、去重与有界GitHub重试；observed_sync.py保存不含响应正文和密钥的诊断。

本地回归：`python3 -m unittest discover -s tests -v`。此次手动流程接入只更新说明与项目使用规则，不修改服务器程序、API或采集日程。

## 验收与历史文档

- [三货币事件同步验收](EVENT-SYNC-ACCEPTANCE-2026-09-30.md)
- [浏览器手动ZAR验收](MANUAL-REFRESH.md#2026-10-01-实测证据jst)
- [镜像诊断说明](MIRROR-DIAGNOSTICS.md)
- DEPLOYMENT.md、QUOTA_PLAN.md、ACCEPTANCE-2026-09-28.md保留历史实施记录；其中“仅ZAR/预取未启用/等待部署”等状态不再代表当前部署。
