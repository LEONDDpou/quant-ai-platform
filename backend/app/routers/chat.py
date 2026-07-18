"""AI 投研助手聊天接口 — 接 LLM 自由对话。

- POST /api/ai/chat  ：接收 messages 数组（前端维护多轮上下文，最多 30 条），
  返回 AI 回复文本；未配置大模型或调用失败时返回明确的错误状态码与文案。
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Literal

from app.services import llm_service as llm

router = APIRouter()

_SYSTEM_PROMPT = (
    "你是一名专业的 A股 量化投研助手，服务于智能交易终端的专业用户。"
    "请用简洁、客观、专业的中文回答用户的量化与基本面问题；"
    "可结合技术面、资金面、基本面、市场情绪展开分析，但禁止给出确定性的买卖指令或具体价格目标；"
    "涉及微观数据请以公开常识与通用逻辑推演为主，避免编造未经验证的细节。"
)


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"] = "user"
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage] = Field(..., min_length=1, max_length=30)
    temperature: float = Field(0.8, ge=0, le=1.5)


class ChatResponse(BaseModel):
    reply: str
    model: str
    llmEnabled: bool


@router.post("/chat", response_model=ChatResponse)
def post_chat(req: ChatRequest):
    """AI 投研助手对话（LLM 优先；未配置或失败返回 4xx 明确错误）。"""
    if not llm.is_llm_enabled():
        raise HTTPException(status_code=503, detail="AI 服务未启用：后端缺少 LLM_API_KEY")

    # 系统提示 + 用户历史（最多取最近 20 条有效消息）
    messages: list[dict] = [{"role": "system", "content": _SYSTEM_PROMPT}]
    for m in req.messages[-20:]:
        content = (m.content or "").strip()
        if content:
            messages.append({"role": m.role, "content": content})

    if len(messages) <= 1:
        raise HTTPException(status_code=400, detail="消息内容为空")

    reply = llm.chat(messages, temperature=req.temperature)
    if not reply:
        raise HTTPException(status_code=502, detail="大模型调用失败，请稍后重试")
    return ChatResponse(reply=reply, model=llm.LLM_MODEL, llmEnabled=True)
