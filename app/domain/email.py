from dataclasses import dataclass


@dataclass
class Email:
    # 메일 번호(PK)
    # 처음에는 0, 저장 시 Repository가 1부터 순서대로 번호를 부여한다.
    email_id: int
    # 발신자 이름
    sender_name: str
    # 메일 제목
    subject: str
    # 메일 내용
    content: str
