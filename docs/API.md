# 本机 HTTP API

## v1.0.0 新增接口

- `GET /api/source-config` 返回 `regions`、`sources`、`catalog`。全国内置来源不可删除。
- `POST /api/test-source`：测试已有来源传 `{id}`；新来源传 `{name,url,region,rank,format}`。`format` 为 `auto/html/rss`，`rank` 为 0–10（0 优先级最高），自定义入口必须为公开 HTTPS。检查入口、至多三篇候选正文和日期，成功返回 `ok:true` 与 `test_token`；失败不会发放令牌。抽样成功不保证网站未来不变。
- `POST /api/sources`：新增需原测试参数及 `test_token`；删除传 `{action:"delete",id}`。令牌 30 分钟有效、一次使用，修改任何来源参数后必须重测。不能删除省份最后一个来源，应使用删除省份。
- `POST /api/regions`：新增传来源参数及令牌，省份与来源同一事务保存；删除传 `{action:"delete",id:"guangdong"}`，同时移除对应采集来源，保留历史档案与笔记。采集中不允许修改来源配置。
- `GET /api/library` 新增 `date_from`、`date_to`（YYYY-MM-DD，包含起止日）、`region`（省份代码 / `national` / `unassigned` / `all`）参数，可与全文检索、类型和专题合用。文稿地区根据所引材料推导，跨地区材料可属于多个地区。
- `GET /api/dashboard` 新增 `regions`、`region_catalog`、`version`，`edition_stats` 按已配置地区返回。
- `GET /api/runtime` 新增 `version:"1.0.0"` 与 `data_directory`；`application` 为 `zhuyi-local-v1`。默认端口 8879，数据环境变量 `ZHUYI_V1_DATA`。

`POST /api/collect` 只使用爬虫、来源权重和确定性规则；即使已配置模型密钥，也不调用大模型。只有用户发起秘书问答、阅后分析、会议纪要、AI 整理等功能时才调用配置的模型。

v1.0.0 基础地址默认为 `http://127.0.0.1:8879`。仅支持本机调用，没有公网账号体系。POST 必须发送 `Content-Type: application/json`，请求体上限1 MB。JSON 顶层为对象。浏览器请求必须同源；命令行 Agent 可以不带 Origin。不要伪造来源，也不要修改服务绑定地址来开放公网。

| 方法与路径 | 用途 | 说明 |
| --- | --- | --- |
| GET `/api/runtime` | 查看是否运行及自动采集开关 | 本地公开版 `application` 为 `zhuyi-local-v1` |
| GET `/api/sources` | 列出已配置来源 | 全国内置来源固定保留 |
| POST `/api/collect` | 启动内置采集 | `{}` 为最近已结束窗口；`{"day":"YYYY-MM-DD"}` 指定期次，不能指定未来未结束窗口；仅使用爬虫和权重规则，不调用大模型 |
| GET `/api/job` | 查看采集进展 | `running`、`message`、`error`；每15—30秒查看一次即可 |
| GET `/api/dashboard?day=YYYY-MM-DD` | 查看该期日报 | `edition` 可能为空，报告可能显示缺项 |
| POST `/api/import` | 导入一篇官方原文到档案 | 见下文；不会调用模型 |
| GET `/api/article?id=ID` | 查看文章 | 注意会记录打开状态，不是无副作用的探测接口 |
| GET `/api/library?q=关键词` | 查看档案 | 建议用来验证导入 |

## 秘书检索开关

POST `/api/chat` 接受 `question`、可选的 `article_id` / `conversation_id`、布尔值 `web` 和可选参考网页 `url`。

- `web` 省略或为 `false`：仅检索本地数据库。问题中的“联网 / 搜索”等文字、历史授权和 `url` 均不会触发网页请求；附带的 `url` 不读取。答复只能依据本地材料，缺少材料时明确说明。
- `web: true`：执行外部搜索，取得网页正文或可引用摘录，也可读取附带的 `url`；本地材料仅作上下文。没有可用外部资料时保存明确的失败答复，不用本地档案冒充联网结果。
- 配置 DeepSeek 官方 HTTPS 地址（`api.deepseek.com`）时，复用当前模型和密钥，通过 `/anthropic/v1/messages` 的 `web_search_20250305` 工具执行原生搜索，每次最多5次搜索，采用最多8个含摘录或可读正文的来源。成功时 `research.provider` 为 `deepseek`。优先使用结构化引用摘录（类型 `DeepSeek 联网摘录`）；摘录不足时从结构化搜索结果中选最多8条链接，优先机构来源，并发读取原网页（类型 `外部网页正文`），仍检查公共 URL，不向网页发送模型密钥。不会把模型自由生成的文字或加密结果当成网页正文。该模型需支持搜索工具，失败时明确提示，不静默改用旧搜索入口。其他提供商仍使用原有网页搜索。
- 原生搜索和最终答复分别调用模型，均记录接口返回的 token 用量；不勾选不会调用搜索接口。不会向 DeepSeek 转发第三方代理的密钥。
- 原生搜索的网页读取沿用既有来源规则：已登记的官方域名可读取 HTTP / HTTPS（兼容人民网、新华网等历史链接），其他域名仍只接受 HTTPS。每次请求及重定向均检查域名、端口和公共网络地址，不能读取本机或内网。
- `web` 必须是 JSON 布尔值，字符串和数字返回 400。该开关控制资料检索；生成答复仍使用用户配置的模型接口。
- 返回的 `research` 包含 `mode`（`local` / `web`）、`status`（`local_only` / `ok` / `unavailable`）、`source_count`，以及搜索关键词与尝试记录。`external_error` 表示本轮未取得联网资料的原因。检索模式及失败提示也会保存在答复正文中。

界面的办公室和文章提问共用“联网查证”选择，默认关闭，并在本浏览器保留到用户主动切换；每次请求均显式发送当前选择。阅后研判保持仅查本地。

## 导入格式

```json
{
  "url": "https://www.gov.cn/替换为真实文章路径.htm",
  "title": "实际原标题",
  "published": "2026-01-02T10:30:00+08:00",
  "body": "核实过的原文正文，至少100字符；不要放模型编写的摘要冒充原文。"
}
```

这是格式示意，URL 和日期必须更换。允许的域名包括 `gov.cn`、`people.com.cn`、`news.cn`、`xinhuanet.com`、`qstheory.cn`、`southcn.com`、`nfnews.com` 及其子域。URL 必须是公开 HTTP(S) 地址，不能是本机或内网；HTTPS 优先。域名会进行地址检查，因此手动提供正文时也需要网络解析域名。

只提供 `url` 时，应用尝试自行读取网页。提供 `body` 时，需要原标题；时间未知可留空，不能伪造发布时间。只有日期时传 `YYYY-MM-DD`，数据库保留日期精度，不能把其归一化时间当作真实发布时分。

成功返回 `{"id":"文章ID"}`。相同 URL 去重，已有正文和批注不会被重新导入覆盖；已彻底删除的 URL 保留去重标记，返回错误而不复活。导入会把文章放到档案，不自动生成今日日报，也不把 Agent 的摘要写成站点原文。Agent 可另存摘要供用户审阅。

失败时返回非2xx状态及 `{"error":"原因"}`。常见情况：400输入不合法、403来源不允许、413请求太大、415内容类型不正确。不要无限重试；检查链接、正文和服务状态后再尝试。

本 API 同时供界面使用，尚未承诺长期兼容。Agent 不应修改设置、删除档案或调用关机接口，除非其使用者明确要求。

## 专注阅读 UI 静态资源

`design/focused-reading` 增加 `/focus.css`、`/focus.js`、`/icons.woff2` 与 `/reading-font.woff` 本地静态资源。字体响应分别使用 `font/woff2` 和 `font/woff`。现有 `/api/*` 请求字段、响应和业务行为保持不变。来源与采集仅移动了前端入口。
