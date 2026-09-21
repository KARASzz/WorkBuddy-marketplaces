# WorkBuddy xParse 执行规程

本规程仅规定本专家如何使用已声明的 TextIn xParse 连接器；连接器自身的 `xparse-parse` Skill、运行时能力、错误结构和认证边界优先。本专家不复制其 CLI 安装、认证、拆分或缓存实现。

## 1. 连接器负责就绪，专家不做环境考古

1. 本专家通过 `.codebuddy-plugin/plugin.json` 的 `dependencies.connectors` 声明依赖公开市场的 `textin-xparse` 连接器。用户尚未安装或连接时，提示其在 WorkBuddy 的连接器卡片中完成安装/连接；不自行寻找目录、CLI 或凭据。
2. 连接器负责安装、更新和管理其固定版本的 `xparse-cli`。文档任务中不得执行 `version` 探测、`npm install`、官方安装脚本、`update`、`find`、`which`、`ls` 或全盘搜索。
3. Windows 文件路径使用 WorkBuddy 附件上下文提供的原始绝对路径，并作为一个完整引用参数传入；不得改写为 Git Bash、WSL 或 `/c/...` 路径。
4. 每个确需发起 xParse 调用的新用户请求，依连接器规则创建一个权限为 `0600` 的私有 task-context JSON，并只在该请求**首次** xParse 调用中带 `--task-context <FILE>`；调用后删除该临时文件。复用会话中已有解析结果时，不创建上下文也不调用 xParse。除原始用户意图和简短调用原因外，`xparse_task_context.v1` JSON 必须添加内部专家来源：

   ```json
   {
     "schema_version": "xparse_task_context.v1",
     "user_intent": "保留用户本轮原始请求和语言",
     "tool_call_reason": "为招投标审阅取得结构化文档证据",
     "caller": {
       "type": "workbuddy_expert",
       "id": "tender-bid-reviewer",
       "version": "1.1.5"
     }
   }
   ```

   `caller.id` 只使用 manifest 的插件名，不使用 Marketplace 发布者前缀；`prompt_request_id` 只继承 WorkBuddy 宿主提供的值，本专家不生成、覆盖、猜测或写入 task-context。
5. 在 WorkBuddy 内每个 xParse 命令显式使用 `xparse-cli --profile workbuddy`。不得把凭据、文档正文、隐藏推理或最终结论放进 task-context、命令行参数或日志。

## 2. 解析一次，导航复用

先用 `get_doc_info <FILE>` 获得本地 `doc_id`、文档类型和页数；它不消耗解析页数。随后按用户范围执行完整缓存解析：

```text
xparse-cli --profile workbuddy parse <FILE> --api auto --output <已存在的目录>
```

- `--api auto` 由服务先走当前可用的免费路径并执行配额预检；它不等于付费，也不等于同意扣费。不得因为已有 OAuth、AppKey 或账户余额改成 `--api paid`。
- 对 PDF，必须给 `parse` 传入已存在的输出目录，再读取生成的结果文件；需要页级信息、坐标、表格或字符详情时才补 JSON/相应定向能力。
- 成功的**完整**本地 `parse` 才会建立导航缓存。之后使用 `get_outline`、`search_text`、`read_pages`（单次不超过 20 页）和 `read_content`，始终复用同一 `doc_id`；不要重复解析同一文件。
- 不执行或假定存在 `ensure_parsed`，不手工按 30/50 页拆分，不自行拼接解析结果。页数、文件大小或拆分限制由当前连接器/服务返回的结构化结果决定；按其 `next_action` 处理。
- 用户要求完整解读或完整预审时，先读大纲，再以不超过 20 页的缓存读取覆盖全部相关页，维护“页码范围｜章节｜要求/事实｜风险或待核验｜证据位置｜已覆盖”的业务索引。局部问题先用大纲/搜索定位，再读最小充分范围。

## 3. 额度预检与付费边界

需要为新文件做完整解析、用户询问额度、或准备提出付费选项时，可在 `get_doc_info` 后查询一次：

```text
xparse-cli --profile workbuddy quota --output json
```

- 仅采用**本次**服务响应的 `daily_pages_remaining`、重置时间，以及明确返回的 `free_package.free_remain_count`。`free_count` 是历史展示值，不得当作余额；不得在会话中累计或缓存额度。
- 以实际计划范围估算最多需要的解析页数：完整任务为文档页数；用户明确限定的任务为未缓存的目标页范围。若预计免费页不足，或完成后仅可能余 20 页及以下，先简短告知页数、当前额度和重置时间。
- 让用户选择：缩小范围、等待重置，或明确同意本次付费解析。预检只是提示，`parse --api auto` 的实时服务决策和实际返回仍为准。
- 绑定认证与同意付费是两件事。只有用户明确同意“本次使用付费 xParse API 解析 {文件/范围}”后，才可调用 `--api paid`。

若用户选择付费而连接器未就绪，指引其在 WorkBuddy 的 **TextIn xParse 连接器**完成“连接/重新连接”或连接器提供的安全凭据绑定流程。用户自行在连接器界面输入 AppKey，或完成 Device OAuth；绝不在聊天、task-context、命令行、工作区文件或报告中索取、保存、回显 `x-ti-app-id`、`x-ti-secret-code`、Token 或设备码。

## 4. 失败处理与用户可见进度

优先读取连接器结构化错误的 `error_code`、`retryable`、`next_action`、服务端限制和 `request_id`，而非猜测中文报错或沿用旧的固定阈值：

- `PAID_QUOTA_REQUIRED`：停止；查询当前额度并等待用户选择缩小范围、等待重置或明确同意付费。
- `PAGE_LIMIT_EXCEEDED`、`FILE_TOO_LARGE`：依据服务返回的限制缩小范围/文件，或在用户明确同意后走付费；不得手写切分策略，也不得静默切付费。
- `AUTHENTICATION_FAILED`、`OAUTH_FAILED`：请用户重新连接 TextIn xParse 连接器；不得索取密钥或尝试替代认证。
- `RATE_LIMITED`、`NETWORK_ERROR`、`SERVICE_ERROR`：仅在 `retryable=true` 时最多重试一次；`RETRY_EXHAUSTED` 不立即重复调用。
- 文件加密、损坏、缺少密码或解析不完整时，停止基于该文件作实质判断，并明确所缺信息。

对用户最多展示两条必要进度：开始解析（可带文件名/页数）和解析完成或需要其决定。不要展示命令探测、内部推理、虚构后台任务或多轮等待过程。

## 5. 交付物

解析成功后，在对话中直接输出带证据位置的审阅结论。HTML、右侧面板报告或文件导出仅在用户明确提出时创建；不要因为报告较长自行生成 HTML。
