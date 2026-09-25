# Sakura 接入与验收

## 当前状态

目标仓库为公开仓库，初始为空；原型通过本机已有 GitHub 登录发布。
发布状态与公开读取验收以实际 HTTP 检查为准；示例不代表实时行情已接入。
尚未获得 Sakura 源码/真实 analysis 样本，也没有连接服务器；以下是待实施方案。

## 最小改动方案

优先采用独立 sidecar 定时任务，不改 API/launcher：
1. 读取现有 ZARJPY analysis 的本地缓存，保持现有更新/获取逻辑不动。
2. 小型适配器输出一个包含 analysis + metadata 的私有 bundle；先写临时文件，再原子 rename。
3. analysis 原样保留公开市场数据；上线前审核所有字段，包括 URL、调试信息、上游请求元数据。
   如果含密钥或账户信息，拒绝整个导出；在专用公开导出层剔除非行情字段并记录差异，不能盲目整包推送。
4. generated_at_utc 取 analysis 原始生成时刻；fetched_at_utc 取真实上游成功获取时刻。
   如果缓存中没有这些时间，需要在生成缓存处增加旁路 metadata 写入；不能改用文件修改时间或同步任务开始时间。
5. 对 1min/H1/H4/D1 逐一核实时间字段的时区、开盘/收盘含义及是否为形成中蜡烛。
   若只有 H1/H4/D1，则当前原型拒绝发布；必须先商定不同的低频契约，不能捏造 1min。
6. 每分钟运行独立同步任务，单实例锁防止重入。同步只读取已有结果，不额外请求 Twelve Data。
7. 脚本跳过 generated_at_utc 相同或更旧的导出；失败限次重试，不覆盖上次有效快照。
   403 等权限错误直接失败；409/部分 5xx/网络异常最多三次。失败超过5分钟由服务监控告警。
   原始服务不等待 GitHub，因此镜像故障不会拖慢现有接口。
8. 原型为“最新快照”，不是行情历史数据库。根据真实数据大小、更新频率、GitHub 限流和仓库增长压测，
   再决定长期频率。不要为每次相同缓存生成新的 generated 时间。

Linux/Sakura 若有 python3 + flock，可用如下 cron 模板；部署者替换实际路径：
```cron
* * * * * /usr/bin/flock -n /private/path/fx-mirror.lock /private/path/run-fx-mirror.sh
```
run-fx-mirror.sh 放在 webroot 和仓库外，权限 700；
令牌通过仅服务账户可读的环境配置注入（600），不得在 cron 命令行展开。
调用 python3 /private/path/mirror.py /private/path/zarjpy-export.json --publish。
如果没有 flock，用服务管理器提供单实例执行；不要无锁并行写同一个 GitHub 文件。

## 远端发布与公开验收

需要目标仓库 Contents 写权限；重新连接后先重查仓库内容，避免覆盖用户新增文件。
上传本目录的明确文件清单，不上传 private/、令牌或服务器配置。

发布后从无凭据的独立 HTTP 客户端请求：
```sh
curl --fail --location --silent --show-error https://raw.githubusercontent.com/nnnnkatsu/fx-chatgpt-mirror/main/zarjpy.json
```
不要带 Authorization、Cookie、登录会话。确认 HTTP 200、可解析 JSON、source/pair 正确。
再用 ChatGPT 网页读取工具打开同一 URL，记录成功或失败；HTTP 200 不保证所有 ChatGPT 定时任务可读。

原型示例预期 status=example、所有行情时间 null；这只是通道验收。
接入后至少观察两个真实更新周期，验证 analysis 与源对象一致、generated/fetched 随真实更新推进，
以及各周期最后蜡烛吻合。模拟停止同步超过5分钟，读取方必须拒绝旧数据。
模拟 GitHub 失败/重复任务/输入泄密字段：原 API 正常、镜像保留旧值、无敏感日志。
公开链接检查属于交付门槛；权限不足时不得报告已完成发布。
