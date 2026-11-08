from app.core.exceptions import EmailNotFoundError
from app.domain.email import Email
from app.schemas.email import EmailResponse, EmailCreateRequest
from app.repositories.email_repository import EmailRepository

# 메일 등록, 조회 비즈니스 로직을 담당하는 서비스
class EmailService:

    def __init__(self, repository: EmailRepository):
        self.repository = repository

    # 신규 메일 생성 - 요청 DTO를 받아 저장하고, 번호가 붙은 메일을 응답 DTO로 반환한다.
    def create_email(self, request: EmailCreateRequest) -> EmailResponse:
    
        email = Email(
            email_id=0,
            sender_name=request.sender_name,
            subject=request.subject,
            content=request.content
        )

        saved = self.repository.save(email)

        return EmailResponse.from_email(saved)

    # 단일 메일 조회 - 번호로 메일을 찾아 응답 DTO로 반환한다. 
    # 없을 시 예외를 던진다.
    def find_email(self, email_id: int) -> EmailResponse:

        email = self.repository.find_by_id(email_id)

        if email is None:
            raise EmailNotFoundError(email_id)

        return EmailResponse.from_email(email)