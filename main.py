import asyncio
import json
from fastmcp import Client
from fastmcp.client.transports import SSETransport
from src.utils import tool_to_openai, get_all_function_tools

# this function for test.

async def main():
    async with Client("server.py") as client:
        tools = await client.list_tools()
        print("Available tools:", tools)
    sse = SSETransport("http://localhost:9000/sse")
    async with Client("http://localhost:8000/mcp") as client:
        print('tools')
        tool_list = await get_all_function_tools([client], True)
        parsed_tools = [tool_to_openai(tool) for tool in tool_list]
        print(parsed_tools)
        tools = await client.list_tools()
        print(tool_list[-1].on_invoke_tool)
        # response = await tool_list[-1].on_invoke_tool(json.dumps({'originLocationCode':'ICN', 'destinationLocationCode':'JFK', 'departureDate':'2025-05-23', 'adults':1, 'children':1}))
        response = await tool_list[-1].on_invoke_tool(json.dumps({'cityCode': 'SEL'}))
        print('----------------------\nresponse:',response)
        
        print(tools)

asyncio.run(main())