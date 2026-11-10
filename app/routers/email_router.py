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
@router.post("", status_code=201, summary="메일 등록",
description="""
받은 업무 메일을 등록한다.

**사용 방법**
1. `senderName`에 보낸 사람 이름을 입력한다. (2~30자)
2. `subject`에 메일 제목을 입력한다. (1~100자)
3. `content`에 메일 내용을 입력한다. (1~5000자)
4. 실행(Execute)하면 등록된 메일을 응답으로 확인할 수 있다. 응답의 `emailId`가 메일 번호이며, 새로 등록한 메일은 11번부터 번호가 붙는다.

"""
)
def create_email(request: EmailCreateRequest, service: EmailServiceDep) -> EmailResponse:
    return service.create_email(request)

# 메일 단건 조회 : 주소의 {email_id}를 받아 메일을 찾는다.
# 없을 시 예외 처리기가 404로 응답한다.
@router.get("/{email_id}", summary="메일 단건 조회",
description="""
메일 번호로 저장된 메일 하나를 조회한다.

**사용 방법**
1. `email_id`에 조회할 메일 번호를 입력한다. (더미 메일 1~10번, 직접 등록한 메일은 11번부터)
2. 실행(Execute)하면 보낸 사람, 제목, 내용을 확인할 수 있다.
3. 없는 번호를 입력하면 404 응답이 온다.
"""
)
def find_email(email_id: int, service: EmailServiceDep) -> EmailResponse:
    return service.find_email(email_id)

# 답장 초안 생성 : 저장된 메일을 꺼내 LLM에 await로 요청하고, 답장 초안을 응답한다.
# async def 핸들러로 이벤트 루프(MainThread)에서 실행된다.
# OpenAI 호출 실패 시 502로 응답한다.
@router.post("/{email_id}/reply", summary="AI 답장 초안 생성",
description="""
저장된 메일에 대한 답장 초안을 AI가 작성한다.

**사용 방법**
1. `email_id`에 답장할 메일 번호를 입력한다. (더미 메일 1~10번, 직접 등록한 메일은 11번부터)
2. `keyPoint`에 답장에 담을 핵심 내용을 입력한다. (예: 외근으로 인해 10시 회의에 참석하기 어렵다)
3. `senderRelationship`에 보낸 사람과의 관계를 상사, 동료, 거래처, 고객 중 하나로 입력한다.
4. 실행(Execute)하면 응답의 `content`에서 AI가 작성한 답장 초안을 확인할 수 있다. 제목(`subject`)은 원본 메일 제목 앞에 `RE: `를 붙인 형태로 고정된다.

"""
)
async def create_reply(email_id: int, request: ReplyCreateRequest, service: ReplyServiceDep) -> ReplyResponse:

    log("reply", "요청 받음")
    response = await service.create_reply(email_id, request)
    log("reply", "응답 보냄")

    return response
