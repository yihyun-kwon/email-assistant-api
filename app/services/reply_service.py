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

사용자가 답장에 담고자 한 내용은 빠짐없이 반영한다. 받은 메일의 질문이나 요청 중 답장에 담을 내용으로 답할 수 있는 것에는 답한다.
사용자가 제공하지 않은 사실, 날짜, 숫자, 일정, 약속은 지어내지 않는다.

제목은 작성하지 않는다. 원메일 제목에 "RE: "를 붙여 사용하므로 답장 본문만 작성한다.
인사말과 자기소개 없이 바로 답변 내용부터 시작하고, 마무리 인사로 끝낸다.
마무리 인사 뒤에 이름, 부서, 직급 같은 서명은 작성하지 않는다.
마무리 인사를 제외한 답변 내용은 보통 3~6문장으로 작성하되,
받은 메일의 요청이 여러 개이거나 설명할 내용이 많으면 8문장까지 작성할 수 있다.
답장에 필요한 내용을 빠짐없이 담고, 불필요한 반복은 피하며 메일 내용에 맞는 길이로 간결하게 작성한다.
사내 규정은 [참고 규정]에 적힌 내용만 근거로 사용하고, 거기에 없는 규정은 지어내지 않는다.
[참고 규정]이 받은 메일이나 답장에 담을 내용과 관련이 없으면 사용하지 않는다.
답장에 실제로 반영한 조항의 번호만 cited_rules에 적는다. (예: 제15조) 반영한 규정이 없으면 비워 둔다.
답장에 담을 내용만으로 답할 수 없는 질문은 지어내지 말고 needs_confirmation에 적는다.
받은 메일의 서명이나 본문에 발신자의 직급(팀장, 과장, 대리 등)이 적혀 있으면 sender_title에 그대로 적는다. 적혀 있지 않으면 비워 두고 추측하지 않는다.
별도의 설명이나 안내 없이 완성된 답장 본문만 출력한다.
"""

# 답장 초안 생성 비즈니스 로직을 담당하는 서비스
class ReplyService:

    # 생성자 주입
    # 원본 메일을 찾을 EmailRepository와 답장 초안을 작성할 LLM 클라이언트, 서명에 넣을 이름을 전달받는다.
    def __init__(self, repository: EmailRepository, llm_client: LlmClient, replier_name: str):

        self.repository = repository
        self.llm_client = llm_client
        self.replier_name = replier_name

    # 답장 초안 생성
    # 원본 메일과 요청을 프롬프트로 만들어 LLM에 보내고, 답장을 응답 DTO로 반환한다.
    async def create_reply(self, email_id: int, request: ReplyCreateRequest) -> ReplyResponse:

        email = self.repository.find_by_id(email_id)

        if email is None:
            raise EmailNotFoundError(email_id)



        draft = await self.llm_client.ask_async(
            instructions=INSTRUCTIONS,
            sender_name=email.sender_name,
            sender_relationship=request.sender_relationship,
            subject=email.subject,
            content=email.content,
            key_point=request.key_point
            )

        # 받는 사람 호칭 : 메일 본문에서 직급이 있을 시 "이름 직급님", 없을 시 "이름님"
        recipient = f"{email.sender_name} {draft.sender_title}님" if draft.sender_title else f"{email.sender_name}님"


        # LLM이 쓴 본문 앞에 인사말, 뒤에 서명을 붙여 답장을 완성한다.
        # 서명의 이름은 .env의 REPLIER_NAME 값을 쓰고, 부서와 직급은 고정이다.
        content =(
                f"안녕하세요, {recipient}. 경영지원팀 {self.replier_name}입니다.\n\n"
                f"{draft.content.strip()}\n\n"
                f"경영지원팀 {self.replier_name} 사원 드림"
                )

        return ReplyResponse(
            subject=f"RE: {email.subject}",
            content=content,
            model=self.llm_client.model,
            cited_rules=draft.cited_rules,
            needs_confirmation=draft.needs_confirmation,
        )
