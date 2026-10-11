import logging
import sqlite3
import sys
import os
from fastapi import FastAPI, Header, HTTPException
from openai import OpenAIError, RateLimitError
from pydantic import BaseModel, field_validator
from 天气.model_client import ModelConfigurationError, run_agent
from openai.types.chat import ChatCompletionMessageParam
from typing import cast
from uuid import uuid4
from 天气.database import (
    initialize_database,
    save_session_with_key,
    save_chat_messages,
    load_messages,
    find_session_id_by_key_hash,
)
from 天气.access_keys import (
    create_conversation_key,
    hash_conversation_key,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

app = FastAPI(title="天气 Agent API")
initialize_database()



class ChatRequest(BaseModel):
    message: str

    @field_validator("message")
    @classmethod
    def clean_message(cls, message: str) -> str:
        cleaned_message = message.strip()

        if cleaned_message == "":
            raise ValueError("消息不能为空")

        return cleaned_message

class SessionResponse(BaseModel):
    session_id: str
    conversation_key: str

class HistoryResponse(BaseModel):
    session_id: str
    messages: list[dict[str, str]]

class ChatResponse(BaseModel):
    answer: str

def require_chat_access_key(x_chat_key: str | None) -> None:
    expected_key = os.getenv("CHAT_ACCESS_KEY")

    if not expected_key:
        raise HTTPException(status_code=503, detail="聊天访问口令未配置")

    if x_chat_key != expected_key:
        raise HTTPException(status_code=401, detail="聊天访问口令错误")

def require_conversation_key(
    conversation_key: str | None,
) -> str:
    if not conversation_key:
        raise HTTPException(
            status_code=401,
            detail="缺少对话钥匙",
        )

    key_hash = hash_conversation_key(conversation_key)
    session_id = find_session_id_by_key_hash(key_hash)

    if session_id is None:
        raise HTTPException(
            status_code=401,
            detail="对话钥匙无效",
        )

    return session_id

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

@app.post(
    "/sessions",
    response_model=SessionResponse,
    status_code=201,
)
def create_session(
    x_chat_key: str | None = Header(default=None),
) -> SessionResponse:
    require_chat_access_key(x_chat_key)

    logger.info("开始创建会话")
    session_id = str(uuid4())
    conversation_key = create_conversation_key(session_id)
    key_hash = hash_conversation_key(conversation_key)

    try:
        save_session_with_key(
            session_id=session_id,
            key_hash=key_hash,
        )
    except sqlite3.Error:
        logger.exception(f"会话保存失败：session_id={session_id}")
        raise

    logger.info(f"会话保存成功：session_id={session_id}")

    return SessionResponse(
        session_id=session_id,
        conversation_key=conversation_key,
    )

@app.get(
    "/history",
    response_model=HistoryResponse,
)
def get_session_history(
    x_conversation_key: str | None = Header(default=None),
) -> HistoryResponse:
    session_id = require_conversation_key(x_conversation_key)

    return HistoryResponse(
        session_id=session_id,
        messages=load_messages(session_id),
    )

@app.post("/chat", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    x_conversation_key: str | None = Header(default=None),
) -> ChatResponse:
    session_id = require_conversation_key(x_conversation_key)

    logger.info(f"开始处理聊天请求：session_id={session_id}")

    try:
        history = cast(
            list[ChatCompletionMessageParam],
            load_messages(session_id),
        )
    except sqlite3.Error:
        logger.exception(
            f"读取历史消息失败：session_id={session_id}"
        )
        raise

    try:
        answer = run_agent(
            user_message=request.message,
            history=history.copy(),
        )

    except RateLimitError:
        logger.exception(f"模型额度不足或请求过于频繁：session_id={session_id}")
        raise HTTPException(
            status_code=503,
            detail="模型额度不足，或者请求过于频繁",
        )

    except OpenAIError:
        logger.exception(f"模型服务调用失败：session_id={session_id}")
        raise HTTPException(
            status_code=503,
            detail="模型服务暂时不可用",
        )

    except ModelConfigurationError as error:
        logger.exception(f"模型配置错误：session_id={session_id}")
        raise HTTPException(
            status_code=503,
            detail=str(error),
        )

    logger.info(f"Agent 回复生成成功：session_id={session_id}")

    try:
        save_chat_messages(
            session_id=session_id,
            user_content=request.message,
            assistant_content=answer,
        )
    except sqlite3.Error:
        logger.exception(
            f"聊天消息保存失败：session_id={session_id}"
        )
        raise

    logger.info(f"聊天消息保存成功：session_id={session_id}")

    return ChatResponse(answer=answer)
