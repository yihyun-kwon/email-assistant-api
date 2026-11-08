from app.core.exceptions import EmailNotFoundError
from app.schemas.email import ReplyResponse, ReplyCreateRequest
from app.clients.llm_client import LlmClient
from app.repositories.email_repository import EmailRepository

# LLM 지시문 (시스템 프롬프트)
INSTRUCTIONS = """
너는 직장인의 업무 메일 답장을 대신 작성하는 비서다.
받은 메일과 사용자가 답장에 담고 싶은 내용을 바탕으로 답장 본문을 작성한다.
보낸 사람과의 관계에 맞는 말투와 높임말을 사용한다.
- 상사에게는 예의를 갖춘 격식 있는 존댓말을 사용한다.
- 거래처에는 격식 있고 정중한 존댓말을 사용한다.
- 고객에게는 친절하고 배려하는 정중한 존댓말을 사용한다.
- 동료에게는 정중하면서도 부드럽고 자연스러운 존댓말을 사용한다.

사용자가 답장에 담고자 한 내용은 빠짐없이 반영한다. 받은 메일의 질문이나 요청에도 적절히 답한다. 
사용자가 제공하지 않은 사실, 날짜, 숫자, 일정, 약속은 지어내지 않는다.

제목은 작성하지 않는다. 원메일 제목에 "Re: "를 붙여 사용하므로 답장 본문만 작성한다. 
본문은 인사, 답변 내용, 마무리 인사 순서로 구성한다. 
인사와 마무리 인사를 제외한 답변 내용은 3~6문장으로 작성한다. 
답장에 필요한 내용을 빠짐없이 담고, 불필요한 반복은 피하며 메일 내용에 맞는 길이로 간결하게 작성한다. 
별도의 설명이나 안내 없이 완성된 답장 본문만 출력한다.
"""

# 답장 초안 생성 비즈니스 로직을 담당하는 서비스
class ReplyService:

    # 생성자 주입
    # 원본 메일을 찾을 EmailRepository와 답장 초안을 작성할 LLM 클라이언트를 전달받는다.
    def __init__(self, repository: EmailRepository, llm_client: LlmClient):
        
        self.repository = repository
        self.llm_client = llm_client

    # 답장 초안 생성
    # 원본 메일과 요청을 프롬프트로 만들어 LLM에 보내고, 답장을 응답 DTO로 반환한다.
    async def create_reply(self, email_id: int, request: ReplyCreateRequest) -> ReplyResponse:

        email = self.repository.find_by_id(email_id)

        if email is None:
            raise EmailNotFoundError(email_id)

        prompt = f"""
            [받은 메일]
            보낸 사람: {email.sender_name}
            나와의 관계: {request.sender_relationship}
            제목: {email.subject}
            내용: {email.content}
            [답장에 담을 내용]
            {request.key_point}
            """

        answer = await self.llm_client.ask_async(
            instructions=INSTRUCTIONS,
            question=prompt)
        
        return ReplyResponse(
            subject=f"RE: {email.subject}",
            content=answer,
            model=self.llm_client.model
        )