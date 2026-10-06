import logging
import sqlite3
import sys

from fastapi import FastAPI, HTTPException
from openai import OpenAIError, RateLimitError
from pydantic import BaseModel, field_validator
from 天气.model_client import ModelConfigurationError, run_agent
from openai.types.chat import ChatCompletionMessageParam
from typing import cast
from uuid import uuid4
from 天气.database import (
    initialize_database,
    save_session,
    save_chat_messages,
    load_messages,
    session_exists,
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
    session_id: str

    @field_validator("session_id")
    @classmethod
    def clean_session_id(
        cls,
        session_id: str,
    ) -> str:
        cleaned_session_id = session_id.strip()

        if cleaned_session_id == "":
            raise ValueError("会话编号不能为空")

        return cleaned_session_id

    @field_validator("message")
    @classmethod
    def clean_message(cls, message: str) -> str:
        cleaned_message = message.strip()

        if cleaned_message == "":
            raise ValueError("消息不能为空")

        return cleaned_message

class SessionResponse(BaseModel):
    session_id: str

class HistoryResponse(BaseModel):
    session_id: str
    messages: list[dict[str, str]]

class ChatResponse(BaseModel):
    answer: str


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

@app.post(
    "/sessions",
    response_model=SessionResponse,
    status_code=201,
)
def create_session() -> SessionResponse:
    logger.info("开始创建会话")
    session_id = str(uuid4())

    try:
        save_session(session_id)
    except sqlite3.Error:
        logger.exception(f"会话保存失败：session_id={session_id}")
        raise

    logger.info(f"会话保存成功：session_id={session_id}")

    return SessionResponse(
        session_id=session_id
    )

@app.get(
    "/sessions/{session_id}/history",
    response_model=HistoryResponse,
)
def get_session_history(
    session_id: str,
) -> HistoryResponse:
    if not session_exists(session_id):
        raise HTTPException(
            status_code=404,
            detail="会话编号不存在",
        )

    return HistoryResponse(
        session_id=session_id,
        messages=load_messages(session_id),
    )

@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    logger.info(f"开始处理聊天请求：session_id={request.session_id}")

    try:
        exists = session_exists(request.session_id)
    except sqlite3.Error:
        logger.exception(
            f"检查会话是否存在失败：session_id={request.session_id}"
        )
        raise

    if not exists:
        logger.warning(
            f"聊天请求被拒绝，会话编号不存在：session_id={request.session_id}"
        )
        raise HTTPException(
            status_code=404,
            detail="会话编号不存在",
        )

    try:
        history = cast(
            list[ChatCompletionMessageParam],
            load_messages(request.session_id),
        )
    except sqlite3.Error:
        logger.exception(
            f"读取历史消息失败：session_id={request.session_id}"
        )
        raise

    try:
        answer = run_agent(
            user_message=request.message,
            history=history.copy(),
        )

    except RateLimitError:
        logger.exception(f"模型额度不足或请求过于频繁：session_id={request.session_id}")
        raise HTTPException(
            status_code=503,
            detail="模型额度不足，或者请求过于频繁",
        )

    except OpenAIError:
        logger.exception(f"模型服务调用失败：session_id={request.session_id}")
        raise HTTPException(
            status_code=503,
            detail="模型服务暂时不可用",
        )

    except ModelConfigurationError as error:
        logger.exception(f"模型配置错误：session_id={request.session_id}")
        raise HTTPException(
            status_code=503,
            detail=str(error),
        )

    logger.info(f"Agent 回复生成成功：session_id={request.session_id}")

    try:
        save_chat_messages(
            session_id=request.session_id,
            user_content=request.message,
            assistant_content=answer,
        )
    except sqlite3.Error:
        logger.exception(
            f"聊天消息保存失败：session_id={request.session_id}"
        )
        raise

    logger.info(f"聊天消息保存成功：session_id={request.session_id}")

    return ChatResponse(answer=answer)
