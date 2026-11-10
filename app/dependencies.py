from typing import Annotated

from fastapi import Depends, Request

from app.core.config import Settings, get_settings
from app.clients.llm_client import LlmClient
from app.repositories.email_repository import EmailRepository
from app.services.reply_service import ReplyService
from app.services.email_service import EmailService

# EmailRepository 객체는 서버가 시작할 때 한 번만 만든다.
email_repository = EmailRepository()

# EmailRepository 객체를 반환하는 의존성 함수
def get_email_repository() -> EmailRepository:
    return email_repository

# EmailService 객체를 만들어 주는 의존성 함수
def get_email_service(repository: Annotated[EmailRepository,
Depends(get_email_repository)]) -> EmailService:
    return EmailService(repository)

# 한 줄로 EmailService를 주입받기 위한 별칭
EmailServiceDep = Annotated[EmailService, Depends(get_email_service)]

# LLM 클라이언트를 꺼내 주는 의존성 함수
def get_llm_client(request: Request) -> LlmClient:
    return request.app.state.llm_client

# ReplyService 객체를 만들어 주는 의존성 함수
def get_reply_service(repository: Annotated[EmailRepository,
Depends(get_email_repository)], llm_client: Annotated[LlmClient,
Depends(get_llm_client)], settings: Annotated[Settings, Depends(get_settings)]) -> ReplyService:
    return ReplyService(repository, llm_client, settings.replier_name)

# 한 줄로 ReplyService를 주입받기 위한 별칭
ReplyServiceDep = Annotated[ReplyService, Depends(get_reply_service)]
