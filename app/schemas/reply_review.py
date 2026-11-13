from pydantic import BaseModel, Field


# LLM이 답장 초안을 검토한 결과 양식
class ReplyReview(BaseModel):
    """LLM이 답장 초안을 검토한 결과 (review 노드의 출력 양식)"""

    # 통과 여부 : 라우팅 함수가 이 값을 보고 END로 갈지, draft로 돌아가 다시 쓸지 정한다.
    passed: bool = Field(description="검토 기준을 모두 만족하면 true, 하나라도 어기면 false")

    # 미통과 이유 : State의 feedback으로 옮겨져 다음 draft가 고칠 점으로 사용한다.
    # 터미널 로그에도 찍어 검토 기준이 너무 까다로운지 확인한다.
    reason: str = Field(description="false라면 다음 초안에서 고칠 점을 기준 번호와 함께 구체적으로 적는다. true라면 '통과'라고 적는다.")
