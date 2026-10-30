# AGENTS.md — AI周报系统

基于本地大模型（llama.cpp / llama-server）的 RAG 知识库周报系统：读取项目 git 提交日志，经向量检索注入 prompt，由本地对话模型以 SSE 流式生成工作周报。

## 执行流程（重要）

1. 根据需求给出详细计划，并确认任务细节
2. 根据任务进行具体的代码执行
3. 验证测试，如果有报错则进行修复
4. 如果更新了相关功能逻辑或新增文档，更新 `AGENTS.md`

## 技术栈与版本约束

- **前端**（目录 `week-fronted/`，注意拼写）：Electron **30** + Vue 3.4 + Element Plus + Vite **5.1.x** + TypeScript(strict) + Pinia
  - ⚠️ **不要升级** electron/vite/vite-plugin-electron 版本（本机 Node 18.20，electron@45 需 Node≥22；用户已确认保持现有版本）
  - 仅可**新增**业务依赖
- **后端**（目录 `backend/`）：Python 3.14 + FastAPI + LangChain 1.x + langchain-openai + SQLite(stdlib sqlite3) + chromadb 1.x
- **本地模型**（llama-server，OpenAI 兼容）：
  - 对话：`Qwen3.5-4B-Q4_K_M.gguf` 端口 **8001**
  - Embedding：`bge-small-zh-v1.5-q4_k_m.gguf` 端口 **8002**（`--embedding` 模式）
  - 路径：`D:\softwares\llama-b10883-bin-win-cpu-x64\`

## 目录结构

```
backend/
├── app/
│   ├── main.py            # FastAPI 入口、CORS、lifespan(init_db)
│   ├── config.py          # .env 配置读取（DB/模型地址等）
│   ├── db.py              # SQLite：projects / chats / messages（级联删除）
│   ├── models.py          # Pydantic 模型
│   ├── routers/
│   │   ├── projects.py    # 项目增删查（校验 git 仓库）
│   │   ├── chats.py       # 对话增删查 + 历史消息
│   │   ├── git_log.py     # GET /api/git/log 时间范围提交预览
│   │   └── chat_stream.py # POST /api/chats/{id}/messages (SSE) + GET /api/health
│   └── services/
│       ├── git_service.py # 子进程 git log --since/--until（0x1e/0x1f 分隔解析）
│       ├── rag_service.py # 提交切块 -> embedding(8002) -> chroma upsert/query/get
│       ├── llm_service.py # LangChain ChatOpenAI -> 8001 流式
│       └── chat_service.py# 组装 system+RAG上下文+历史 -> SSE 事件流，消息落库
├── chroma/                # 向量库持久化（collection = project_{id}）
├── requirements.txt / .env.example
└── start-llama.bat / start-embed.bat / start-backend.bat

week-fronted/
├── electron/
│   ├── main.ts            # 窗口 + IPC dialog:selectFolder（原生选目录）
│   └── preload.ts         # contextBridge: window.electronApi.selectFolder()
└── src/
    ├── api/               # http.ts(统一错误) index.ts(REST + streamChat SSE 解析)
    ├── stores/            # project.ts / chat.ts（Pinia，后端 SQLite 为唯一数据源）
    ├── components/        # ProjectTree / ChatPanel / TimeRangeBar / MessageItem / MarkdownView
    │                       #   ChatPanel 内含右侧「问题目录」侧栏（列出用户提问，点击定位并高亮对应消息，可收起）
    ├── utils/markdown.ts  # README 规定的 unified 管线（含 rehype-mermaid inline-svg）
    └── types/             # api.ts(数据模型+SSE事件) electron.d.ts(Window.electronApi)
```

## 后端 API 接口一览

统一前缀 `http://127.0.0.1:8000`（前端 vite 把 `/api` 代理到该地址）；错误响应为 FastAPI 标准 `{"detail": "..."}` + 状态码。

### 项目（`routers/projects.py`）

| 方法 | 路径 | 说明 | 请求 | 响应 |
| --- | --- | --- | --- | --- |
| POST | `/api/projects` | 添加项目（校验路径存在/为文件夹/git 仓库；重复 409） | body `{path}`（git 仓库绝对路径） | `ProjectOut {id,name,path,created_at}` |
| GET | `/api/projects` | 项目列表（id 倒序） | — | `ProjectOut[]` |
| DELETE | `/api/projects/{project_id}` | 删除项目（级联删对话/消息 + 删除 chroma collection） | — | `{ok:true}`（404 不存在） |

### 对话（`routers/chats.py`）

| 方法 | 路径 | 说明 | 请求 | 响应 |
| --- | --- | --- | --- | --- |
| POST | `/api/chats` | 新建对话（title 缺省/空白 → 「对话 N」） | body `{project_id, title?}` | `ChatOut {id,project_id,title,created_at}`（404 项目不存在） |
| GET | `/api/chats?project_id=` | 对话列表（可选按项目过滤，id 升序） | query `project_id?` | `ChatOut[]` |
| DELETE | `/api/chats/{chat_id}` | 删除对话（messages 级联删除） | — | `{ok:true}`（404 不存在） |
| GET | `/api/chats/{chat_id}/messages` | 历史消息（id 升序） | — | `MessageOut[] {id,chat_id,role(user/assistant),content,created_at}`（404 不存在） |

### 对话流 / 健康检查（`routers/chat_stream.py`）

| 方法 | 路径 | 说明 | 请求 | 响应 |
| --- | --- | --- | --- | --- |
| POST | `/api/chats/{chat_id}/messages` | SSE 流式对话/周报生成（详见下方「SSE 协议」） | body `{content, since?, until?, generate?}` | `text/event-stream` 事件流 |
| POST | `/api/chats/{chat_id}/stop` | 暂停该对话正在进行的生成 | — | `{ok:bool}`（无进行中生成时为 false） |
| GET | `/api/health` | 本地模型健康检查（chat 探测 8001，embed 探测 8002） | — | `{chat:bool, embed:bool}` |

### git 预览（`routers/git_log.py`）

| 方法 | 路径 | 说明 | 请求 | 响应 |
| --- | --- | --- | --- | --- |
| GET | `/api/git/log` | 时间范围提交预览（最多 200 条） | query `project_id, since?, until?` | `{commits:[...], total}`（404 项目不存在 / 400 git 错误） |

## 关键设计

### SSE 协议（POST /api/chats/{id}/messages）

请求体：`{content, since?, until?, generate?}`；下行 `data: {json}\n\n`：

- `{"meta":{commits,rag,project,since,until,generate}}` — 上下文信息（先发）
- `{"token":"..."}` — 流式增量
- `{"done":true,"id":N,"title":"..."}` — 结束（id=助手消息落库 id；首条消息回答成功后后端自动把对话重命名为「时间范围 或 第一个问题(截30字)」并随 done 下发 title，其余情况为 null）
- `{"stopped":true,"question":"..."}` — 用户点击暂停：后端停止 LLM 输出、删除刚落库的用户消息（不保存助手回答），前端移除本地消息并把 question 撤回到输入框
- `{"error":"..."}` — 错误

暂停接口：`POST /api/chats/{id}/stop`（无副作用返回 `{ok:bool}`）。后端 `chat_service` 用模块级 `_active_streams/_stop_flags` 集合标记暂停请求，流式循环在每个 token 间检查。

前端用 `fetch` + `ReadableStream` 手动解析（EventSource 不支持 POST）。

### RAG（rag_service）

- 知识源**仅 git 提交日志**（用户确认，无文档上传）
- 每条 commit 一个 chunk；元数据 `date/author/subject/short_sha`；时间范围用 chroma `where`（`$gte/$lte`）过滤
- 周报生成（`generate=true`）：不带 query → `collection.get()` 取范围内全量（按日期倒序截 80）
- 普通提问带时间范围：用问题做 embedding → `collection.query()` 语义检索 top-12
- **降级**：8002 不可用时自动回退直接读 `git log`（`get_context_commits` 返回 `rag=False`），保证周报功能可用
- 删除项目时同步 `delete_collection(project_{id})`

### 前端要点

- 项目树：`el-tree`，父级=项目（+新建对话/删除项目），子级=对话（删除），`node-key` 用 `p-{id}/c-{id}` 避免 id 冲突；数据变更后 `treeVersion++` 重建以让 `default-expand-all` 生效
- 选文件夹：Electron 原生 `dialog.showOpenDialog`；**纯浏览器环境降级**为 `ElMessageBox.prompt` 手输路径
- markdown 渲染：`MarkdownView` 对流式内容 120ms 节流；`renderMarkdown` 三级降级（完整管线 → 无 mermaid 管线 → 转义纯文本），防止流式中不完整的 mermaid 代码块阻塞渲染
- 周报消息卡片带「复制」按钮（`navigator.clipboard.writeText` 原始 markdown）
- 输入框快捷键：Enter 发送，**Ctrl+Enter 换行**（Shift+Enter 亦不发送、保留默认换行）
- `vite.config.ts`：`/api` 代理到 `127.0.0.1:8000`；别名 `@ → src`（tsconfig 已配 paths）

## 常用命令

```bat
:: 后端（先建 venv）
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
copy .env.example .env
start-backend.bat

:: 前端
cd week-fronted
npm install
npm run dev          :: vite + electron 同时启动
npx vue-tsc --noEmit :: 类型检查
npx vite build       :: 生产构建（不含 electron-builder 打包）
```

## 注意事项

- Python 3.14 环境：依赖已验证可用（pydantic 2.14 / langchain 1.4 / chromadb 1.5.9）；新增依赖需先验证 3.14 兼容性
- 前端 `npm run build` = `vue-tsc && vite build && electron-builder`，会产出安装包，耗时长
- 测试 git 仓库可用 `%TEMP%\week-report-test-repo`（含 3 条演示提交）
- 后端未启动/模型未启动时，前端会在 `App.vue` `onMounted` 里弹 ElNotification 明确提示
