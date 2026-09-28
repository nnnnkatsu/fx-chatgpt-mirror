> 2026-09-28: USDJPY and MXNJPY passive mirrors deployed and live-tested. See [multi-pair acceptance](ACCEPTANCE-MULTI-2026-09-28.md). No active prefetch or global quota gate is enabled.

> 最新验收（2026-09-28）：两次真实源请求均由服务器自动上传，源字段逐项保真、Token写权限及GitHub连接器读取通过。下方2026-09-26记录为部署历史；其待验收项以 [ACCEPTANCE-2026-09-28.md](ACCEPTANCE-2026-09-28.md) 为准。普通web reader仍未通过稳定读取验证。

# Sakura ZARJPY 被动镜像部署

## 已部署状态（2026-09-26 UTC）

已停止原先每两分钟重新请求 Sakura analysis 的轮询，替换为 **只读取本地 JSON** 的镜像。
服务器 Python 3.8.12 标准库；不安装新依赖。

- 运行目录：/home/drexworld/fx-mirror/（700）
- 原响应副本：/home/drexworld/fx-mirror/cache/zarjpy-analysis.json（600）
- 旁路函数：/home/drexworld/fx-mirror/capture.php
- 发布去重记录：/home/drexworld/fx-mirror/published.json
- Token：仅在 Sakura CRON 环境变量 FX_MIRROR_GITHUB_TOKEN
- 频率：每两分钟检查本地文件；缓存缺失或过期不发起行情请求
- 正式 CRON 命令：

```sh
/usr/bin/env PATH=/usr/local/bin:/usr/bin:/bin python3 /home/drexworld/fx-mirror/sakura_runner.py >/dev/null 2>&1
```

## 源响应保存

现有 /home/drexworld/www/fx/index.php 只增加一个独立旁路区块。
它在现有请求已得到 HTTP 200 的 ZARJPY analysis 后，调用 capture.php 保存同一份 body。
其他货币、price、各独立周期、HEAD 和失败响应不进入旁路。
原来的 body、响应头、状态码、API 路径、launcher、PATH nonce 逻辑不变。
没有为了镜像再请求一次 Sakura、Cloudflare 或 Twelve Data。

文件锁避免同时写入，原子替换避免读到半份 JSON；旧 fetched 不覆盖更新结果。
旁路失败被隔离，不改变原 API 响应。GitHub 发布在独立 CRON 中完成，不阻塞行情响应等待 GitHub。

## 部署证据

- 被动脚本来自 commit 74205122129176f5d90ab6ff4bdae4bb9d94132e；安装器 eb8d0b14cf4759e8974d7aa23eddfacae3dd7d69。
- 旁路安装器 commit 4266c2bef9f0deec2a917218fd9a235c8293b1cc。
- 2026-09-26T08:56:00.524853+00:00：旁路安装完成；PHP lint 与隔离功能测试均通过；测试没有真实行情调用。
- 2026-09-26T08:58:00.085Z：正式被动 CRON 运行，stage=awaiting_local_source，upstream_requests=0。
- launcher 无需调用行情即验证 HTTP 200，PATH nonce 对应本次请求，仍输出四币种各 price/analysis 共八条原路径。
- 匿名 RAW 返回 HTTP 200，但 fetched_at_utc 仍为 2026-09-25T07:15:04.284Z，不可用于实时交易。

原代理 SHA-256：
303a7fb1109edad2f7d0e4a93bf4987cd01ce46c68d62ab8bf1f46c6ee123add

安装后代理 SHA-256：
b588f0ae4ca12b8fcb36ed0332fc85b90032cae7952be0063f51a3d30dae6815

原文件备份（私有，不在 webroot）：
/home/drexworld/fx-mirror/index.php.before-mirror.303a7fb1109edad2f7d0e4a93bf4987cd01ce46c68d62ab8bf1f46c6ee123add.bak

仅删除标记为 “ZARJPY passive mirror: persist the existing response only.” 的新增区块即可撤销旁路；
恢复备份前先检查当前文件是否有其他后续改动，不得覆盖无关修改。
暂停镜像可将唯一镜像 CRON 命令设为 /usr/bin/true，原 API 不受影响。

## 尚未完成的验收

当前没有从一次真实正常请求捕获到新的本地 analysis，因此不能声称完整生产链路验收完成。
未为了周末验收额外调用行情。隔离测试数据只保存在 selftest 目录，绝不进入实际 cache 或 GitHub。
两次真实新鲜数据的 GitHub 自动更新、Token 实际写权限、普通 ChatGPT fallback 稳定性仍待验证。
upstream_requests=0 表示该被动镜像代码路径没有行情请求，不是 Twelve Data 账户总调用量计量。

## 安全与发布

仅保存公开行情；发布前继续执行敏感字段扫描与所有 freshness 校验。
GitHub 失败保留上一份；409/429/5xx 和网络异常最多三次尝试，401/403 不循环重试。
同一份成功源结果由本地 source hash 去重，不再重复 GET/PUT GitHub。
Token 不在命令、代码、公开文件或日志中。新鲜度不合格不重写时间，不补抓行情。

运行状态：https://drexworld.sakura.ne.jp/fx-mirror-status.json
安装证据：https://drexworld.sakura.ne.jp/fx-mirror-install.json
公开 RAW：https://raw.githubusercontent.com/nnnnkatsu/fx-chatgpt-mirror/main/data/zarjpy.json

## 主动调度未启用

共享配额模块已离线测试，但没有接管现有 Worker 请求。
检测前一次预采集、合并临时查询、跨币种配额账本仍需实际时间表、套餐额度、
analysis 最大 credits 成本及全部上游入口接入验证后才能上线。详见 QUOTA_PLAN.md。
