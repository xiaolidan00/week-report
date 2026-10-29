rem 启动对话模型 llama-server (Qwen3.5-4B, 端口 8001)
set LLAMA_DIR=D:\softwares\llama-b10883-bin-win-cpu-x64
start "llama-chat-8001" "%LLAMA_DIR%\llama-server.exe" -m "%LLAMA_DIR%\models\Qwen3.5-4B-Q4_K_M.gguf" --port 8001
echo 对话模型启动中: http://127.0.0.1:8001
