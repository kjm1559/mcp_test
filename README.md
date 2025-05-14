Example of MCP server and tool transformation
===

This method support just only single shot response using chat.complete.

## MCP server on

- Simple one
```shell
uv run server.py
```
- Other way
```bash
# 기본 STDIO 실행
fastmcp run server.py

# HTTP 서버로 배포 (Streamable HTTP)
fastmcp run server.py --transport streamable-http --host 0.0.0.0 --port 8000

# SSE(Server-Sent Events) 모드
fastmcp run server.py --transport sse --port 9000
```

## Gradio on

```shell
uv run run.py
```

## Reference
- [Open AI agent repository](https://github.com/openai/openai-agents-python/tree/main)