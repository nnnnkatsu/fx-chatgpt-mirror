> 当前变更覆盖下方历史记录：仓库已改为被动本地缓存同步。原服务器轮询暂停因登录失效未保存成功；新脚本和响应落盘钩子尚未部署。下方“每2分钟自动运行”描述的是旧版本，不表示配额保护已上线。详见 QUOTA_PLAN.md。

# Sakura → GitHub 最小接入

## Deployment status: 2026-09-26 UTC

Independent scripts: `/home/drexworld/fx-mirror/` (directory mode 700). Server runtime: Python 3.8.12 standard library. Original Sakura API, index.php, launcher and PATH nonce are unchanged. ZARJPY only.

CRON: every 2 minutes, all days. Saved production command:

```sh
/usr/bin/env PATH=/usr/local/bin:/usr/bin:/bin python3 /home/drexworld/fx-mirror/sakura_runner.py >/dev/null 2>&1
```

Token stays in Sakura CRON environment variable `FX_MIRROR_GITHUB_TOKEN`. The original proxy has no local analysis cache, so the independent runner requests the existing Sakura ZARJPY analysis endpoint using a fresh PATH nonce. It does not change the existing request handler.

Installed mirror.py and sakura_runner.py are pinned to commit `8ea291d99fc452911da1029a2d9c2c9296b0ba47`. Bootstrap installer commit: `69a8eff1df2882879278c2d143243b209cfb54cd`; downloads were SHA-256 checked. After installation, CRON was shortened to run local files directly.

Public sanitized health status: https://drexworld.sakura.ne.jp/fx-mirror-status.json

Observed automatic run: 2026-09-26T00:56:01.495Z, stage=freshness, ValueError. Independent source check: fetched_at_utc=2026-09-26T00:57:30.455Z, but 1min latest_candle_at_utc=2026-09-25T23:59:00Z and candle_age_seconds=3510. A new fetch does not make old candles fresh.

Acceptance remains pending: two successful automated GitHub updates must show advancing fetched_at_utc and _mirror.mirrored_at_utc. Existing public JSON remains an old snapshot, unsuitable for live analysis. Cron continues automatically and attempts publication only after all freshness checks pass. Server token write permissions have not yet been proven by a successful publication.

The following sections are design/operations reference, not additional changes to the original API.

## 推荐：在现有 analysis 成功生成后旁路投递

现有流程成功取得完整 ZARJPY analysis 后，把同一份 JSON 原子写到服务器私有文件/队列。
同步工作进程读取该文件，运行：
```sh
python3 /private/fx-mirror/mirror.py /private/fx-mirror/zarjpy-analysis.json --public-export-reviewed --publish
```
不要再次请求 Twelve Data，不改任何 URL、launcher 或 PATH nonce。
若已有完整 analysis 缓存，直接读该缓存，连主程序的写文件步骤也无需增加。
如果只有内存响应，可添加一个旁路原子文件投递；具体插入位置需读取实际源码后确定。
上传必须在独立任务中完成，不能让现有 HTTP 响应等待 GitHub。
使用单实例任务/文件锁，避免多个同步进程同时处理；失败不影响现有接口。

可选每分钟消费已有快照（不是 GitHub Actions 反向抓取）：
```cron
* * * * * /usr/bin/flock -n /private/fx-mirror/sync.lock /private/fx-mirror/run-sync.sh
```
仅在主机存在 flock 时使用；否则用该主机的单实例调度。
此仓库不安装调度任务，也不启动本机持续抓取替代 Sakura。

## Token 安全配置

在 GitHub fine-grained PAT 页面创建仅访问 nnnnkatsu/fx-chatgpt-mirror 的 token，
Repository permissions 仅需要 Contents: Read and write，并设置到期时间。
https://github.com/settings/personal-access-tokens

token 只放在 Sakura 的环境/安全配置中，不能放进仓库、webroot、命令行参数、日志或聊天。
服务账户私有目录权限700，配置文件600。run-sync.sh 从私有配置载入并 export
FX_MIRROR_GITHUB_TOKEN，然后运行上述脚本。不要启用 shell set -x。
本仓库不保存任何真实 token，也不传递 Twelve Data key 或 Sakura 密码。
服务器 token 与本机用于开发提交的 GitHub 登录是两回事；本机凭据不会复制到服务器。

脚本发布前扫描凭据字段/常见 token 格式；发现后整包拒绝，不静默删掉行情字段。
--public-export-reviewed 表示部署者已审核源导出仅含公开市场数据。
扫描不能识别任意未知密钥，新增源字段后必须重新审核；不要把调试请求信息混进行情。

## 重试与一致性

- 目标仅 main:data/zarjpy.json，GET 当前 SHA，再 PUT。
- 对409、429、500/502/503/504、网络异常最多3次，退避1/2秒；
  Retry-After 在0–60秒范围内处理。每次重试重新GET SHA、重新校验新鲜度。
- 401/403及其他非重试错误直接失败，避免权限错误循环请求。
- 超时后重新GET；若相同/更新 fetched 已发布则跳过，避免重复提交。
- 不用 force push；相同或更旧 fetched 跳过；源过期/错误/缺字段/泄密则保留上一份。
- 日志不输出输入 JSON、请求头、token 或响应体。非零退出由服务器监控告警。
- GitHub CDN 可能缓存；消费者必须检查源时间，不能靠 HTTP 成功判定新鲜。

## 验收

1. 独立无登录 HTTP 客户端请求固定 RAW，确认200并能解析。
2. 普通 ChatGPT 对话打开同一 RAW，确认能看到全部六周期，记录实际结果。
3. 当前为单次快照，测试稍晚必然过期；可测试可读性，但不能把旧行情用于交易。
4. 部署后观察至少两次真实源更新，确认 fetched 和蜡烛随源推进，价格/指标与原 JSON 一致。
5. 停止投递>5分钟，读取方必须拒绝旧快照；恢复后再接受。
6. 模拟GitHub失败、重复任务、源中含凭据：原API正常、旧快照保留、敏感信息不出日志。

GitHub API 官方说明：
https://docs.github.com/en/rest/repos/contents#create-or-update-file-contents

## Verification evidence

- Automatic run 1: 2026-09-26T00:56:01.495Z; freshness rejected.
- Automatic run 2: 2026-09-26T01:00:01.399Z; freshness rejected, after switching to the local production command.
- Anonymous RAW HTTP 200 confirmed. Published fetched_at_utc remains 2026-09-25T07:15:04.284Z; _mirror.mirrored_at_utc remains 2026-09-25T07:15:05.123Z.
- These are two scheduler executions, NOT two successful uploads. No live-data acceptance claim is made.
