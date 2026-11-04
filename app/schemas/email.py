from pydantic import Field
from app.domain.email import Email
from app.schemas.base import CamelModel


class EmailCreateRequest(CamelModel):

    # 발신자 이름 : 1글자 이상 30글자 이하
    sender_name: str = Field(min_length=2, max_length=30)
    # 메일 제목 : 1글자 이상 100글자 이하
    subject: str = Field(min_length=1, max_length=100)
    # 메일 내용 : 1글자 이상 5000글자 이하
    content: str = Field(min_length=1, max_length=5000)


class EmailResponse(CamelModel):

    email_id: int
    sender_name: str
    subject: str
    content: str


    @classmethod
    # Entity를 응답 DTO로 변환
    def from_email(cls, email: Email) -> 'EmailResponse':

        return cls(
            email_id=email.email_id,
            sender_name=email.sender_name,
            subject=email.subject,
            content=email.content
        )
