rem 启动 embedding 模型 llama-server (bge-small-zh-v1.5, 端口 8002, --embedding 模式)
set LLAMA_DIR=D:\softwares\llama-b10883-bin-win-cpu-x64
start "llama-embed-8002" "%LLAMA_DIR%\llama-server.exe" -m "%LLAMA_DIR%\models\bge-small-zh-v1.5-q4_k_m.gguf" --embedding --port 8002
echo Embedding 模型启动中: http://127.0.0.1:8002
