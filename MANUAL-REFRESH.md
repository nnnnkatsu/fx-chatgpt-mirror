# 浏览器手动触发行情（正式流程）

适用 USDJPY、ZARJPY、MXNJPY。沿用现有 Sakura v3.1 API、launcher 和 PATH nonce，不新增接口，不提高定时采集频率。只有 ZARJPY 已完成本次浏览器端到端实测；另外两种使用同一已部署机制，不能冒称本次也做了浏览器实测。

## 操作

1. 临时需要新行情时，在普通浏览器重新打开 https://drexworld.sakura.ne.jp/fx/launch/ 。只打开 launcher 不会采集行情。检查 Generated UTC；旧页面重新打开一次，或按原规则使用当前全新数字 PATH nonce。不要收藏、复用旧 analysis 链接。
2. 点击本次 launcher 返回的对应货币 **fresh analysis** 一次。不要点击 price 代替 analysis，也不要拆成六周期请求。
3. 新 analysis 成功后，Sakura 自动落盘并触发 GitHub 镜像，原120秒补偿任务保留。复制不额外请求 Twelve Data；analysis 可能采集新行情，受所有货币共用的每日800、每分钟8 credits限制。一份完整 analysis 通常涉及7次上游调用，不能按1 credit估算；实际扣费以服务记录为准。
4. 随即回到投资项目，发送：我刚刚在浏览器点击了 ZARJPY fresh analysis，请读取当前 GitHub 镜像、验证新鲜度并分析，附手动诊断日志。把货币替换为实际点击的货币。
5. ChatGPT 先读取对应镜像；不要因为用户已经触发，反而再请求一次 Sakura analysis。main 旧或版本不明确时，查询本轮最新文件提交，再读取完整 commit SHA 对应的 JSON。GitHub 本身不会刷新行情。

## 浏览器显示拦截或空白时

2026-10-01 的 ZAR 实测中，Chrome 显示 ERR_BLOCKED_BY_CLIENT，但服务器已经处理请求并更新镜像。因此页面显示错误不等于请求没有执行，也不等于一定已经成功。先只读 GitHub 核对源时间和提交，不连续点击重试，不关闭浏览器安全防护，不使用猜测的 analysis URL 绕过错误。

如果新镜像尚未可见，且当前工具确实支持等待，可以在这次手动验证流程中等待15秒后仅再查一次最新提交及快照；这是用户已完成浏览器触发后的发布核验，不套用定时检查T+90秒窗口。没有等待工具就如实说明。最多两轮GitHub核验，不追加上游请求。仍旧或无效时停止，记录失败日志，不编造价格或Entry/SL/TP。

## 校验和日志

必须使用实际当前UTC验证 fetched_at_utc 年龄0–300秒，以及六周期的时间一致性和各自年龄上限（周期时长+300秒）。不能只看新的 commit 或 mirrored_at_utc；generated_at_utc 未提供仍为null；超过60秒的快照不能当即时成交报价。

正文保留交易判断、账本和执行条件；诊断集中到末尾JSON日志。记录 run_type=manual、trigger_method=browser_launcher_analysis、trigger_confirmed_by=user_report或observed_browser_click、source_freshness_verified、读取时点、源时点、镜像时点、实际SHA、各周期检查、请求次数及失败原因。浏览器返回结果不确定时明确记录，不假装成功。未知值填null，不放密钥、持仓或交易计划到日志，不自动写GitHub。此流程不赋予普通ChatGPT浏览器控制能力；没有相应工具时由用户点击。

## 2026-10-01 实测证据（JST）

- 只点击一次 ZARJPY fresh analysis；未增加额外行情请求。
- 源 fetched_at_utc=2026-10-01T06:24:54.246Z（15:24:54）。
- mirrored_at_utc=2026-10-01T06:24:54.377Z；GitHub commit时间06:24:55Z。
- commit：d5da6cb88b90ed20c49645786395ac2c04f8b646。
- 固定快照：https://raw.githubusercontent.com/nnnnkatsu/fx-chatgpt-mirror/d5da6cb88b90ed20c49645786395ac2c04f8b646/data/zarjpy.json
- GitHub连接器已读回新快照。此历史快照只作为验收证据，不能作为以后交易数据。

一句话自动调用刷新工具尚未实现；本流程是浏览器手动触发的正式接入。
