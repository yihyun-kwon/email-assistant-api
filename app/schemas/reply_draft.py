from pydantic import BaseModel, Field

# LLM이 돌려줄 답장 초안 양식 
class ReplyDraft(BaseModel):
    """LLM이 작성한 답장 초안 (API 응답 DTO가 아니라 LLM 출력용 양식)"""

    # 답장 본문: 인사말과 서명은 ReplyService가 붙이므로 본문만 받는다.
    content: str = Field(description="인사말, 자기소개, 서명을 뺀 답장 본문. 답변 내용으로 시작해 마무리 인사로 끝낸다.")

    # 근거 조항 목록: 답장에 반영한 사내 규정 조항 번호 (기본값 빈 리스트)
    cited_rules: list[str] = Field(
        default=[],
        description="답장의 근거로 사용한 사내 규정 조항 번호 목록. 예: ['제6조', '제20조']. 근거로 쓴 규정이 없으면 빈 목록.")

    # 확인 필요 사항: 답하지 못한 질문 목록 (LLM이 지어내지 않고 사용자에게 넘긴다)
    needs_confirmation: list[str] = Field(
        default=[],
        description="받은 메일의 질문 중 답장에 담을 내용과 규정만으로 답할 수 없는 것. 없으면 빈 목록",
    )