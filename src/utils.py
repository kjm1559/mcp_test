import functools
import json
from typing import Any
from fastmcp import Client
import logging
import openai
from openai import OpenAI
import os
import tomllib
from src.strict_schema import ensure_strict_json_schema
from src.tools import FunctionTool
from openai.types.chat.chat_completion_tool_param import ChatCompletionToolParam
logger = logging.getLogger("openai.agents")

def tool_to_openai(tool: FunctionTool) -> ChatCompletionToolParam:
    if isinstance(tool, FunctionTool):
        pram = tool.params_json_schema
        additionalProperties = pram['additionalProperties']
        pram.pop('additionalProperties')
        return {
            "type": "function",
            "function": {
                "description": tool.description or "",
                "name": tool.name,
                "parameters": tool.params_json_schema,
                "additionalProperties": additionalProperties,
            },
        }

async def get_all_function_tools(
    servers: list[Client], convert_schemas_to_strict: bool
) -> list[dict]:
    """Get all function tools from a list of MCP servers."""
    tools = []
    tool_names: set[str] = set()
    for server in servers:
        server_tools = await get_function_tools(server, convert_schemas_to_strict)
        server_tool_names = {tool.name for tool in server_tools}
        # if len(server_tool_names & tool_names) > 0:
        #     raise UserError(
        #         f"Duplicate tool names found across MCP servers: "
        #         f"{server_tool_names & tool_names}"
        #     )
        tool_names.update(server_tool_names)
        tools.extend(server_tools)

    return tools

async def get_function_tools(
    server: Client, convert_schemas_to_strict: bool
) -> list[dict]:
    """Get all function tools from a single MCP server."""
    tools = await server.list_tools()
    return [to_function_tool(tool, server, convert_schemas_to_strict) for tool in tools]

def to_function_tool(
    tool: dict, server: Client, convert_schemas_to_strict: bool
) -> FunctionTool:
    """Convert an MCP tool to an Agents SDK function tool."""
    invoke_func = functools.partial(invoke_mcp_tool, server, tool)
    schema, is_strict = tool.inputSchema, False

    # MCP spec doesn't require the inputSchema to have `properties`, but OpenAI spec does.
    if "properties" not in schema:
        schema["properties"] = {}

    if convert_schemas_to_strict:
        try:
            schema = ensure_strict_json_schema(schema)
            is_strict = True
        except Exception as e:
            logger.info(f"Error converting MCP schema to strict mode: {e}")

    return FunctionTool(
        name=tool.name,
        description=tool.description or "",
        params_json_schema=schema,
        on_invoke_tool=invoke_func,
        strict_json_schema=is_strict,
    )

async def invoke_mcp_tool(
    server: Client, tool: dict, input_json: str
) -> str:
    """Invoke an MCP tool and return the result as a string."""
    try:
        json_data: dict[str, Any] = json.loads(input_json) if input_json else {}
    except Exception as e:
        logger.error('input data error', e)
    try:
        result = await server.call_tool(tool.name, json_data)
    except Exception as e:
        logger.error(f"Error invoking MCP tool {tool.name}: {e}")
        # raise AgentsException(f"Error invoking MCP tool {tool.name}: {e}") from e

    # The MCP tool result is a list of content items, whereas OpenAI tool outputs are a single
    # string. We'll try to convert.
    
    tool_output = result[0].text # just for text
    return tool_output

def get_client():
    config = get_config()    
    base_url = config["openai_base_url"]
    api_key = config["openai_api_key"]
    client = OpenAI(
        base_url = base_url,
        api_key = api_key
    )
    return client

def llm_streaming_call(
        client: OpenAI,
        system_prompt:str = '', 
        messages:list[dict] = [], 
        tools: list = [],
        temperature:float = 0.3, 
        ):
    config = get_config()
    if system_prompt:
        messages = [{'role': 'system', 'content': system_prompt}] + messages
    response = client.chat.completions.create(
        model = config['base_ml'],
        messages = messages,
        temperature = temperature,
        tools=tools if tools else openai.NOT_GIVEN,
        max_tokens=4096,
        stream=True
    )
    for chunk in response:
        yield chunk

def streaming_call(
        message: str,
        tools: list = [],
    ):
    config = get_config()
    chat_client = openai.OpenAI(
        base_url=config['openai_base_url'],
        api_key=config['openai_api_key'],
    )
    response = chat_client.chat.completions.create(
        model=config['base_ml'],
        messages=[{'role': 'user', 'content': message}],
        # max_tokens=max_tokens if max_tokens is not None else openai.NOT_GIVEN,
        tools=tools if tools else openai.NOT_GIVEN,
        max_tokens=4096,
        # parallel_tool_calls=True if tools else openai.NOT_GIVEN,
        tool_choice="required",
        parallel_tool_calls=True,
    )
    return response

def llm_call(
        system_prompt:str, 
        messages:list[dict], 
        temperature:float, 
    ) -> str:
    config = get_config()
    client = OpenAI(
        base_url=config['openai_base_url'],
        api_key=config['openai_api_key'],
    )
    if system_prompt:
        messages = [{'role': 'system', 'content': system_prompt}] + messages
        
    response = client.chat.completions.create(
        model = config['base_ml'],
        messages = messages,
        temperature = temperature
    )
    return response.choices[0].message.content

def get_config(path="config.toml") -> dict:
    with open(path, "rb") as f:
        config = tomllib.load(f)
    print(config.keys())
    
    if '$' in config["openai_base_url"]:
        config["openai_base_url"] = os.path.expandvars(config["openai_base_url"])
    if '$' in config["openai_api_key"]:
        config["openai_api_key"] = os.path.expandvars(config["openai_api_key"])
    return config