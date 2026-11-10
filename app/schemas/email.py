from typing import Literal

from pydantic import Field

from app.domain.email import Email
from app.schemas.base import CamelModel


# 메일 등록 요청 DTO
class EmailCreateRequest(CamelModel):

    # 발신자 이름 : 2글자 이상 30글자 이하
    sender_name: str = Field(min_length=2, max_length=30)
    # 메일 제목 : 1글자 이상 100글자 이하
    subject: str = Field(min_length=1, max_length=100)
    # 메일 내용 : 1글자 이상 5000글자 이하
    content: str = Field(min_length=1, max_length=5000)

# 메일 응답 DTO
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

# 답장 초안 생성 요청 DTO
class ReplyCreateRequest(CamelModel):

    # 답장에 담을 내용 : 2글자 이상 500글자 이하
    key_point: str = Field(
        min_length=2, max_length=500)
    # 발신자와의 관계 : 정해진 값만 받는다. 목록에 없는 값이면 422 (말투를 정할 때 사용)
    sender_relationship: Literal["상사", "동료", "거래처", "고객"]

# 답장 초안 응답 DTO
class ReplyResponse(CamelModel):

    # 답장 제목 : "RE: " + 원본 메일 제목
    subject: str
    # LLM이 생성한 답장 본문
    content: str
    # 응답한 모델 이름
    model: str
