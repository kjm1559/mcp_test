import httpx
from fastmcp import FastMCP, Context
import os
import datetime
import requests
import json
import logging
from typing import Optional, Annotated
from pydantic import Field
from mcp_tool.amadeus_tool import (
    amadeus_tools
)
logging.basicConfig(format='%(asctime)s:%(levelname)s:%(message)s',datefmt = '%m/%d/%Y %I:%M:%S %p', level=logging.INFO)
logger = logging.getLogger(__name__)

mcp = FastMCP(name='test')

@mcp.resource("config://version")
def get_version():
    return "2.3.3"

@mcp.prompt()
def ask_name_prompt(prompt: str) -> str:
    return f"what's your name? {prompt}"

# @mcp.tool()
async def add(
    a: Annotated[
        int, 
        Field(description='Number A'),
    ],
    b: Annotated[
        int,
        Field(description="Number B")
    ]) -> int:
    # ctx:Context) -> int:
    """Add 'a' and 'b'"""
    return a + b

# @mcp.tool()
async def summarize(uri: str, ctx: Context):
    """This tool is summarizing target uri."""
    await ctx.info(f"summarizing context at {uri}...")
    # return "called"
    async with httpx.AsyncClient() as client:
        page = await client.get(uri)
    return page.text 

at = amadeus_tools()
mcp.add_tool(at.search_fligiht)
mcp.add_tool(at.list_hotel_by_city)
mcp.add_tool(at.search_flight_by_origin)
mcp.add_tool(at.search_hotel_offer)

if __name__ == "__main__":
    # mcp.run()
    # mcp.run(transport="stdio")  # Default, so transport argument is optional
    mcp.run(transport="streamable-http", host="127.0.0.1", port=8000, path="/mcp")
    # mcp.run(transport="sse", host="127.0.0.1", port=8000)
