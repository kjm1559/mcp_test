Example of MCP server and tool transformation
===

This method support just only single shot response using chat.complete.

## Requirements
- Add the Amadeus API key to your system environment.
```shell
export AMADEUS_SECRET_KEY={your_secret_key}
export AMADEUS_API_KEY={your_api_key}
```
- Set the LLM configuration in the config.toml file.

## MCP server on

- Simple one
```shell
uv run server.py
```
- Other way
```bash
# 기본 STDIO 실행
uv fastmcp run server.py

# HTTP 서버로 배포 (Streamable HTTP)
uv fastmcp run server.py --transport streamable-http --host 0.0.0.0 --port 8000

# SSE(Server-Sent Events) 모드
uv fastmcp run server.py --transport sse --port 9000
```

## Gradio on

```shell
uv run run.py
```

## Reference
- [Open AI agent repository](https://github.com/openai/openai-agents-python/tree/main)