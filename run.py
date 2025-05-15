import gradio as gr
import json
import openai
import datetime
import asyncio
from fastmcp import Client
from src.utils import llm_streaming_call, get_client, get_all_function_tools, tool_to_openai
from src.prompt import base_prompt, tool_call_prompt
import time

import logging
logging.basicConfig(format='%(asctime)s:%(levelname)s:%(message)s',datefmt = '%m/%d/%Y %I:%M:%S %p', level=logging.INFO)
logger = logging.getLogger(__name__)

client = get_client()

def trans_chat_history(chat_histroy):
    return [dd for dd in chat_histroy if dd['role'] in ['user', 'assistant'] and 'content' in dd]

async def chat_by_tools(message, chat_history):
    chat_history.append({'role': 'user', 'content': message})
    async with Client("http://localhost:8000/mcp") as client_mcp:
        function_name, function_id = '', ''
        tool_body = ''
        st_time = time.time()
        tools = await client_mcp.list_tools()
        tool_list_mcp = await get_all_function_tools([client_mcp], True)
        logger.info(f'hand shaking : {time.time() - st_time}')

        tools = [tool_to_openai(tool) for tool in tool_list_mcp]
        
        for chunk in llm_streaming_call(client=client, system_prompt=base_prompt.format(current_time=datetime.datetime.now().isoformat()), messages=chat_history, tools=tools):
            if chunk.choices[0].delta.tool_calls:
                if chunk.choices[0].delta.tool_calls[0].id:
                    function_id = chunk.choices[0].delta.tool_calls[0].id
                if chunk.choices[0].delta.tool_calls[0].function.name:
                    function_name =chunk.choices[0].delta.tool_calls[0].function.name
                tool_body += chunk.choices[0].delta.tool_calls[0].function.arguments

            if chunk.choices[0].delta.content:
                if chat_history[-1]['role'] != 'assistant':
                    chat_history.append({'role': 'assistant', 'content': chunk.choices[0].delta.content})
                else:
                    chat_history[-1]['content'] += chunk.choices[0].delta.content
                yield trans_chat_history(chat_history), chat_history
        logger.info(f'function name: {function_name}')
        if function_name:
            try:
                tool_call = json.loads(tool_body)
                logger.info(f'[tool] {function_name}, {function_id}, {tool_call}')
                tool_result = ''
                for t in tool_list_mcp:
                    if t.name == function_name:
                        tool_result = await t.on_invoke_tool(json.dumps(tool_call))
                        logger.info(f'tool result: {t.name}, {tool_result}')
                
                chat_history.append({'role': 'assistant', 'tool_calls': [{'id': function_id, 'type': 'function', 'function':{'name': function_name, 'arguments': tool_body}}]})
                chat_history.append({'role': 'tool', 'name': function_name, 'tool_call_id': function_id, 'content': json.dumps(tool_result, ensure_ascii=False)})
            except:
                pass
            for tool_chunk in llm_streaming_call(client=client, system_prompt=tool_call_prompt.format(current_time=datetime.datetime.now().isoformat()), messages=chat_history):
                if tool_chunk.choices[0].delta.content is not None:
                    if chat_history[-1]['role'] != 'assistant':
                        chat_history.append({'role':'assistant', "content":tool_chunk.choices[0].delta.content})
                    else:
                        chat_history[-1]['content'] += tool_chunk.choices[0].delta.content
                    yield trans_chat_history(chat_history), chat_history

def text_clean():
    return None

with gr.Blocks() as demo:
    chat_history_with_tool = gr.State([])
    chat = gr.Chatbot(type="messages")
    textbox = gr.Textbox(placeholder='Type a message...', show_label=False, interactive=True, submit_btn=True)
    textbox.submit(chat_by_tools, inputs=[textbox, chat_history_with_tool], outputs=[chat, chat_history_with_tool]).then(text_clean, outputs=[textbox])

if __name__ == '__main__':
    demo.launch(server_name="0.0.0.0", server_port=7867)