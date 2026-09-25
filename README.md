# Sakura FX v3.1 — ZAR/JPY ChatGPT 只读镜像原型

本仓库仅增加行情的第二个出口，不改变现有 Sakura API、launcher 或交易逻辑。
当前 zarjpy.json 是 **example / tradable=false**，没有价格、没有伪造时间戳，不能用于交易。
同步器尚未接入 Sakura；尚未核实真实 analysis 字段与数据提供商的再分发许可。
不要把本原型描述成已经运行的实时服务。

## 文件与读取入口

- zarjpy.json：根目录固定镜像入口；目前是空示例。
- mirror.py：Python 3.9+ 标准库同步原型；校验、完整包装 analysis、GET SHA / PUT GitHub。
- tests/test_mirror.py：时间、保真、重复发布、安全拒绝等离线检查。
- examples/export.example.json：输入结构示例，不包含真实市场数据。
- .gitignore：排除私密输入、环境文件、密钥、日志。
- DEPLOYMENT.md：Sakura 端接入和公开读取验收。

发布后固定读取：
https://raw.githubusercontent.com/nnnnkatsu/fx-chatgpt-mirror/main/zarjpy.json

## JSON 契约 v1.0

|字段|含义|
|---|---|
|source|固定 sakura-v3.1；只是来源标签，不是数字签名|
|pair|固定 ZARJPY|
|status|example 或 live；live 仅代表已校验并导出，不是买卖信号|
|tradable|本原型始终 false；不自动授权交易|
|analysis|Sakura 原始公开 analysis 对象，字段/数组/值尽量保留，不重新算指标；JSON 空白/数字文本格式不保证逐字节一致|
|generated_at_utc|原始 analysis 生成时间；禁止拿上传时间填充|
|fetched_at_utc|该导出依赖的行情最近成功获取时间；多周期使用其中最早的获取时间，不能用缓存命中时间|
|mirrored_at_utc|本次包装时刻；不等于行情更新时间，也不保证 PUT 完成时间|
|latest_candle_at_utc|1min 最新蜡烛的开盘时刻；不能把 H1/H4 的时间冒充 1min|
|candle_age_seconds|包装时刻减 1min 开盘时刻；读取时必须重算|
|freshness_by_timeframe|每个周期的开盘 UTC、是否已收盘、包装时刻计算的年龄|

UTC 全部使用带 Z 的 ISO 8601。未知时间保留 null 并禁止发布 live；不得猜测时区。
未取得真实源结构前，metadata 是待接入的显式适配契约，不是假定 Sakura 已有这些字段。
必须核实 analysis 中品种、各周期末根蜡烛和 metadata 一致；只有经检查的公开字段才可进入导出。
脚本检测凭据样式是第二层防线，不能保证识别任意字段中隐藏的密钥。

## 读取方必须重新验证

1. 先判断 status=live、source、pair、schema_version 和 analysis 非空。example 永远拒绝。
2. 用读取时刻重算 now-generated 和 now-fetched，必须都在 0–300 秒；时间在未来也拒绝。
3. 1min 最新开盘时刻年龄必须在 0–360 秒；H1/H4/D1 各自不超过周期长度+300秒。
   多周期较旧蜡烛不能仅凭新 fetched 时间变成新行情。
4. candle_age_seconds 只是导出快照值；raw CDN 缓存期间它不会自动增长。
5. 依据 K 线收盘的交易规则只能使用 is_closed=true 的蜡烛；实际计划仍须读取足够历史 K 线。
6. 缺字段、周期不全、过期、周末/节假日不更新：报告实时读取失败/市场休市，不能自动放宽时限。
7. tradable=false 表示本原型尚未完成生产验收；通过读取校验也不能直接生成交易执行指令。
   生产启用须完成真实源映射、市场状态/交易日历、数据授权、持续运行验收，再单独变更这个开关。

主路径仍是 Sakura；只有主路径不可读时才读取镜像。镜像不新鲜则失败，不编造行情。
公开 HTTP 成功只证明可访问；不证明数据新鲜、模型能读取完整内容、或定时任务已经配置。
本次没有修改任何现有定时任务。

## 最小调用

先参考 examples/export.example.json，在服务器私有目录生成一份原子写入的完整 bundle。
示例有固定历史时间和 public_export_reviewed=false，运行应拒绝，不能作为真实行情发布。

```sh
python3 mirror.py /private/path/zarjpy-export.json --output /private/path/mirror-preview.json
python3 mirror.py /private/path/zarjpy-export.json --publish
python3 -m unittest discover -s tests -v
```

令牌仅从服务器进程环境 FX_MIRROR_GITHUB_TOKEN 读取。
使用仅限本仓库 Contents: read/write 的 fine-grained token；不要把令牌放入源码、命令行、URL、
公开 JSON、日志或提交记录。不要复用 Twelve Data key。不要请求用户在聊天中粘贴密钥。
GitHub Contents API：
https://docs.github.com/en/rest/repos/contents#create-or-update-file-contents

原型发布只更新根目录 zarjpy.json；无 GitHub Actions、无服务器凭据、无 API/launcher 改动。
