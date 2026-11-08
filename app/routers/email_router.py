import threading
import time

from fastapi import APIRouter

from app.dependencies import EmailServiceDep, ReplyServiceDep
from app.schemas.email import EmailResponse, ReplyResponse, EmailCreateRequest, ReplyCreateRequest


# 메일 API 라우터
router = APIRouter(
    prefix="/api/emails",
    tags=["메일"]
)

# 핸들러가 어느 스레드에서 실행되는지 터미널에 찍는다. 
def log(handler: str, message: str) -> None:
    now = time.strftime("%H:%M:%S")
    thread = threading.current_thread().name
    print(f"{now} [{handler}] {message} (스레드: {thread})")

# 메일 등록 : 요청 본문(JSON)을 EmailCreateRequest로 받아 저장하고 201로 응답한다.
@router.post("", status_code=201, summary="메일 등록")
def create_email(request: EmailCreateRequest, service: EmailServiceDep) -> EmailResponse:
    return service.create_email(request)

# 메일 단건 조회 : 주소의 {email_id}를 받아 메일을 찾는다. 
# 없을 시 예외 처리기가 404로 응답한다.
@router.get("/{email_id}", summary="메일 단건 조회")
def find_email(email_id: int, service: EmailServiceDep) -> EmailResponse:
    return service.find_email(email_id)

# 답장 초안 생성 : 저장된 메일을 꺼내 LLM에 await로 요청하고, 답장 초안을 응답한다.
# async def 핸들러로 이벤트 루프(MainThread)에서 실행된다. 
# OpenAI 호출 실패 시 502로 응답한다.
@router.post("/{email_id}/reply", summary="AI 답장 초안 생성")
async def create_reply(email_id: int, request: ReplyCreateRequest, service: ReplyServiceDep) -> ReplyResponse:

    log("reply", "요청 받음")
    response = await service.create_reply(email_id, request)
    log("reply", "응답 보냄")
    
    return response