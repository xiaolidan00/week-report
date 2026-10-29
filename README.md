# AI周报系统

基于本地大模型的 RAG 知识库周报系统

# 技术架构

## 前端

Vue3 + Element Plus + Vite + TypeScript + Pinia

markdwon解析，支持mermaid

```ts
import {unified} from "unified";
import remarkParse from "remark-parse";
import remarkGfm from "remark-gfm";
import remarkRehype from "remark-rehype";
import rehypeHighlight from "rehype-highlight";
import rehypeMermaid from "rehype-mermaid";
import rehypeStringify from "rehype-stringify";
export const getMarkdownParse = () => {
  const parser = unified()
    .use(remarkParse) // markdown -> mdast
    .use(remarkGfm)
    .use(remarkRehype, {allowDangerousHtml: true})
    .use(rehypeMermaid, {
      strategy: "inline-svg"
    })
    .use(rehypeHighlight)
    .use(rehypeStringify, {allowDangerousHtml: true});
  return parser;
};
```

## 后端

Python + FastAPI + LangChain + SQLite

## 本地模型地址

`D:\softwares\llama-b10883-bin-win-cpu-x64\models`

## llama.cpp地址

`D:\softwares\llama-b10883-bin-win-cpu-x64\`

## 本地模型

llama.cpp（llama-server，OpenAI 兼容接口）：

- 对话模型：Qwen3.5-4B（8001 端口）
- Embedding 模型：本地 `bge-small-zh-v1.5-q4_k_m.gguf`（8002 端口，`--embedding` 模式）

## 执行流程

1. 根据需求给出详细计划，并确认任务细节
2. 根据任务进行成具体的代码执行
3. 验证测试，如果有报错则进行修复
4. 如果更新了相关功能逻辑或新增文档，更新`AGENTS.md`

# 主要功能

- 选择项目文件夹，添加到项目列表
- 左侧是项目列表，右侧对话框
- 项目列表树形结构（父级文件夹名，子级对话框名），点击项目右侧添加按钮，可以创建聊天对话框，点击子级右侧删除按钮，可以删除对话框数据
- 根据选择时间范围，执行git命令，读取提交日志，根据聊天对话框时中问题，总结并给出工作周报内容
- 对话框为 AI 聊天，采用本地模型分析，并以流式（SSE）返回答案输出到对话框，对话框显示支持markdown和mermaid

# 启动步骤（Windows）

## 1. 启动 llama-server（本地模型服务，端口 8001）

```bat
backend\start-llama.bat
```

或手动启动（按实际路径修改模型）：

```bat
D:\softwares\llama-b10883-bin-win-cpu-x64\llama-server.exe ^
  -m D:\softwares\llama-b10883-bin-win-cpu-x64\models\Qwen3.5-4B-Q4_K_M.gguf ^
  --port 8001
```

## 2. 启动 embedding 服务（本地 GGUF embedding，端口 8002）

```bat
backend\start-embed.bat
```

或手动启动：

```bat
D:\softwares\llama-b10883-bin-win-cpu-x64\llama-server.exe ^
  -m D:\softwares\llama-b10883-bin-win-cpu-x64\models\bge-small-zh-v1.5-q4_k_m.gguf ^
  --embedding --port 8002 
```

## 3. 启动后端（端口 8000）

```bat
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
copy .env.example .env
start-backend.bat
```

或手动：

```bat
.venv\Scripts\python -m uvicorn app.main:app --port 8000
```

## 4. 启动前端（Electron + Vite，端口 5173）

```bat
cd week-fronted
npm install
npm run dev
```

`npm run dev` 会同时启动 Vite 开发服务器并打开 Electron 窗口（加载 http://localhost:5173，`/api` 代理到 8000）。

## 5. 打包（可选）

```bat
cd week-fronted
npm run build
```

产物输出到 `week-fronted\release\`（electron-builder，Windows NSIS 安装包）。

## 项目结构

```
week-report/
├── backend/          # Python + FastAPI + LangChain + SQLite + chroma
│   ├── app/          #   main/config/db/models + routers + services(git/rag/llm/chat)
│   ├── chroma/       #   向量库持久化目录（按项目分 collection）
│   ├── start-llama.bat    # 8001 对话模型
│   ├── start-embed.bat    # 8002 embedding 模型
│   └── start-backend.bat  # 8000 后端
└── week-fronted/     # Electron + Vue3 + Element Plus + Vite + TS + Pinia
    ├── electron/     #   main.ts(窗口/原生选目录 IPC) + preload.ts
    └── src/          #   api/(REST+SSE) stores/(Pinia) components/(树/聊天/周报)
```

浏览器访问 http://localhost:5173
