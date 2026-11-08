from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.clients.llm_client import FakeLlmClient
from app.clients.llm_client import OpenAiLlmClient
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.routers import email_router


@asynccontextmanager
async def lifespan(app: FastAPI):

    # 시작 전 처리
    settings = get_settings()

    if settings.fake_llm or settings.openai_api_key is None:
        print(f"[lifespan] 가짜 LLM 클라이언트를 사용한다 (FAKE_LLM={settings.fake_llm}, "
              f"키 있음={settings.openai_api_key is not None}, 응답까지 {settings.fake_llm_delay_seconds}초)")
        app.state.llm_client = FakeLlmClient(settings)
    else:
        print(f"[lifespan] OpenAI 클라이언트를 사용한다 (model={settings.openai_model})")
        app.state.llm_client = OpenAiLlmClient(settings)
        
    yield

    # 종료 시 처리
    await app.state.llm_client.close()


app = FastAPI(
    title="비즈니스 메일 답장 초안 API 서버",
    version="1.0.0",
    lifespan=lifespan,
)

register_exception_handlers(app)

app.include_router(email_router.router)