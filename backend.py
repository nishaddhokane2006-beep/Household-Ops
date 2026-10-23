"""
backend.py – FastAPI backend for the Household Ops demo chat UI.

Flow:
  Browser (chat + mic) ──► POST /chat ──► Bedrock Converse API
                                          ↕ (tool calls)
                                          MCP server (localhost:8000/mcp)

This also acts as a static file server for the frontend (index.html).

Prerequisites:
  - AWS credentials configured (aws configure or env vars)
  - Bedrock model access enabled for claude-3-5-haiku-20241022 in your region
  - MCP server running: python server.py
  - Environment variables (see .env.example):
      AWS_REGION        (default: us-east-1)
      BEDROCK_MODEL_ID  (default: anthropic.claude-3-5-haiku-20241022-v1:0)
      MCP_SERVER_URL    (default: http://localhost:8000/mcp)

Start:
    uvicorn backend:app --reload --port 7860
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

import boto3
import mcp.types as mcp_types
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from pydantic import BaseModel

# --------------------------------------------------------------------------- #
#  Config                                                                       #
# --------------------------------------------------------------------------- #
AWS_REGION       = os.getenv("AWS_REGION", "us-east-1")
BEDROCK_MODEL_ID = os.getenv(
    "BEDROCK_MODEL_ID", "anthropic.claude-3-5-haiku-20241022-v1:0"
)
MCP_SERVER_URL   = os.getenv("MCP_SERVER_URL", "http://localhost:8000/mcp")

bedrock = boto3.client("bedrock-runtime", region_name=AWS_REGION)

app = FastAPI(title="Household Ops Demo", version="1.0")

# Serve static files (index.html, etc.) from this directory
STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(exist_ok=True)


# --------------------------------------------------------------------------- #
#  Pydantic models                                                              #
# --------------------------------------------------------------------------- #
class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []   # [{role, content}] prior turns


class ToolCallRecord(BaseModel):
    tool:   str
    input:  dict
    output: Any


class ChatResponse(BaseModel):
    reply:      str
    tool_calls: list[ToolCallRecord]


# --------------------------------------------------------------------------- #
#  MCP helpers                                                                  #
# --------------------------------------------------------------------------- #
async def _get_mcp_tools() -> list[mcp_types.Tool]:
    """Connect to the MCP server and return its tool list."""
    async with streamable_http_client(MCP_SERVER_URL) as (r, w, _):
        async with ClientSession(r, w) as session:
            await session.initialize()
            result = await session.list_tools()
            return result.tools


async def _call_mcp_tool(name: str, arguments: dict) -> Any:
    """Call a single tool on the MCP server and return its content."""
    async with streamable_http_client(MCP_SERVER_URL) as (r, w, _):
        async with ClientSession(r, w) as session:
            await session.initialize()
            result = await session.call_tool(name, arguments)
            # Return first text content or the whole result
            if result.content and hasattr(result.content[0], "text"):
                try:
                    return json.loads(result.content[0].text)
                except (json.JSONDecodeError, AttributeError):
                    return result.content[0].text
            return str(result)


def _mcp_tool_to_bedrock(tool: mcp_types.Tool) -> dict:
    """Convert an MCP tool definition to the Bedrock Converse toolSpec format."""
    schema = tool.inputSchema or {}
    return {
        "toolSpec": {
            "name":        tool.name,
            "description": tool.description or "",
            "inputSchema": {"json": schema},
        }
    }


# --------------------------------------------------------------------------- #
#  Core: Bedrock Converse with tool-calling loop                                #
# --------------------------------------------------------------------------- #
async def run_bedrock_with_tools(
    user_message: str,
    history: list[dict],
) -> tuple[str, list[ToolCallRecord]]:
    """
    Run the Bedrock Converse API in a multi-turn tool-calling loop.
    Returns (final_reply_text, list_of_tool_call_records).
    """
    # Fetch tool definitions once
    mcp_tools = await _get_mcp_tools()
    bedrock_tools = [_mcp_tool_to_bedrock(t) for t in mcp_tools]

    # Build message list
    messages: list[dict] = []
    for h in history:
        messages.append({"role": h["role"], "content": [{"text": h["content"]}]})
    messages.append({"role": "user", "content": [{"text": user_message}]})

    system_prompt = (
        "You are Household Ops, a helpful home management assistant. "
        "You have access to tools for managing a pantry, suggesting meals that "
        "use up expiring ingredients, building shopping lists, and tracking bills. "
        "Always call the appropriate tool when the user mentions pantry items, "
        "meals, shopping or bills. Return concise, friendly responses."
    )

    tool_calls_made: list[ToolCallRecord] = []
    MAX_TURNS = 8  # safeguard against infinite loops

    for _ in range(MAX_TURNS):
        response = bedrock.converse(
            modelId=BEDROCK_MODEL_ID,
            system=[{"text": system_prompt}],
            messages=messages,
            toolConfig={"tools": bedrock_tools},
        )

        stop_reason = response["stopReason"]
        output_msg  = response["output"]["message"]
        messages.append(output_msg)  # append assistant turn

        if stop_reason == "end_turn":
            # Final answer – extract text
            for block in output_msg.get("content", []):
                if "text" in block:
                    return block["text"], tool_calls_made
            return "Done.", tool_calls_made

        if stop_reason == "tool_use":
            # Process all tool use blocks in this turn
            tool_results = []
            for block in output_msg.get("content", []):
                if "toolUse" not in block:
                    continue
                tool_use   = block["toolUse"]
                tool_name  = tool_use["name"]
                tool_input = tool_use["input"]
                tool_use_id = tool_use["toolUseId"]

                # Call the actual MCP tool
                try:
                    tool_output = await _call_mcp_tool(tool_name, tool_input)
                except Exception as exc:
                    tool_output = {"error": str(exc)}

                tool_calls_made.append(
                    ToolCallRecord(
                        tool=tool_name,
                        input=tool_input,
                        output=tool_output,
                    )
                )

                tool_results.append({
                    "toolUseId": tool_use_id,
                    "content":   [{"text": json.dumps(tool_output, ensure_ascii=False)}],
                })

            # Append tool results as user turn
            messages.append({
                "role": "user",
                "content": [{"toolResult": tr} for tr in tool_results],
            })

        else:
            # Unknown stop reason – bail out
            break

    return "I ran out of steps. Please try again.", tool_calls_made


# --------------------------------------------------------------------------- #
#  API routes                                                                   #
# --------------------------------------------------------------------------- #
@app.get("/")
async def serve_index():
    index = STATIC_DIR / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return JSONResponse({"status": "Household Ops backend running. UI not found in /static"})


@app.get("/health")
async def health():
    return {"status": "ok", "model": BEDROCK_MODEL_ID, "mcp_url": MCP_SERVER_URL}


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")
    try:
        reply, tool_calls = await run_bedrock_with_tools(req.message, req.history)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return ChatResponse(reply=reply, tool_calls=tool_calls)


@app.get("/tools")
async def list_tools():
    """Expose MCP tool list for the UI to display."""
    try:
        tools = await _get_mcp_tools()
        return {"tools": [{"name": t.name, "description": t.description} for t in tools]}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"MCP server unreachable: {exc}")
