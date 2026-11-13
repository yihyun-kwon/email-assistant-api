from app.schemas.reply_review import ReplyReview
from app.rag.rulebook_retriever import build_search_query, format_docs
from langchain_openai import ChatOpenAI
from typing import TypedDict

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.vectorstores import VectorStoreRetriever
from langgraph.graph import StateGraph, START, END
from app.schemas.reply_draft import ReplyDraft

# 재작성 상한 : 초안을 이 횟수만큼 쓰면 미통과여도 끝낸다.
MAX_ATTEMPTS = 2

# 검토 지시문 (review 노드의 system 프롬프트)
REVIEW_INSTRUCTIONS = """
너는 업무 메일 답장 초안을 검토하는 검토자다.
아래 기준을 모두 만족하는지 판단한다.
1) 받은 메일의 질문이나 요청 중 답장에서 빠진 것이 없다.
2) 답장에 담을 내용과 [참고 규정]에 없는 약속, 날짜, 숫자, 일정을 지어내지 않았다.
"""

# 답장 그래프의 상태 : 노드들이 함께 읽고 쓰는 값 묶음
# 노드는 State 전체를 받아 바꿀 필드만 dict로 돌려준다.
class ReplyState(TypedDict):

    # ===== 입력 : 처음 ainvoke 할 때 넣는다 =====
    # 답장 작성 지시문 (reply_service의 INSTRUCTIONS)
    instructions: str

    # 받은 메일 (email)
    sender_name: str
    subject: str
    content: str

    # 사용자 요청 (request)
    sender_relationship: str
    key_point: str

    # ===== retrieve 노드가 채운다 =====
    # 검색된 규정 조항 글 (format_docs 결과)
    context: str

    # ===== draft 노드가 채운다 =====
    # 답장 초안. 첫 draft 전에는 None
    draft: ReplyDraft | None
    # 초안을 쓴 횟수. 처음엔 0, draft 노드가 쓸 때마다 1 올린다.
    attempts: int

    # ===== review 노드가 채운다 =====
    # 검토 통과 여부. 라우팅 함수가 이 값과 attempts를 보고 END 또는 draft로 보낸다.
    passed: bool

    # 미통과 이유 (ReplyReview.reason). 다음 draft가 고칠 점으로 사용한다. 첫 draft 전에는 None
    feedback: str | None


def build_reply_graph(llm: ChatOpenAI, retriever: VectorStoreRetriever):

    # ===== 프롬프트와 체인 : 그래프를 만들 때 한 번만 준비하고 노드에서 재사용한다 =====
    # 초안 작성용 : 기존 /reply 템플릿에 [이전 검토 지적] 칸을 더했다.
    draft_prompt = ChatPromptTemplate.from_messages([
            ("system", "{instructions}\n\n[참고 규정]\n{context}"),
            ("human",
            "[받은 메일]\n보낸 사람: {sender_name}\n"
            "나와의 관계: {sender_relationship}\n"
            "제목: {subject}\n내용: {content}\n\n"
            "[답장에 담을 내용]\n{key_point}\n\n"
            "[이전 검토 지적]\n{feedback}"),
        ])

    draft_chain = draft_prompt | llm.with_structured_output(ReplyDraft)

    # 검토용 : 검토 지시문과 초안을 보여 주고 ReplyReview 양식으로 판정을 받는다.
    review_prompt = ChatPromptTemplate.from_messages([
                    ("system", REVIEW_INSTRUCTIONS + "\n\n[참고 규정]\n{context}"),
            ("human",
            "[받은 메일]\n제목: {subject}\n내용: {content}\n\n"
            "[답장에 담을 내용]\n{key_point}\n\n"
            "[검토할 답장 초안]\n{draft_content}\n\n"
            "[확인 필요 항목]\n{needs_confirmation}"),
        ])

    review_chain = review_prompt | llm.with_structured_output(ReplyReview)

    # 규정 검색
    # 제목·내용·keyPoint로 검색어를 만들어 관련 조항을 찾고, 글로 합쳐 context에 넣는다.
    async def retrieve(state: ReplyState) -> dict:
        query = build_search_query(state)
        docs = await retriever.ainvoke(query)

        return {"context": format_docs(docs)}

    # 초안 작성
    # 메일·요청·검색된 규정으로 답장 초안을 쓴다.
    # 미통과로 다시 들어오면 review가 남긴 feedback을 보고 고쳐 쓴다.
    async def draft(state: ReplyState) -> dict:
        # 이번이 몇 번째 초안인지 센다. 라우팅 함수가 이 값으로 재시도 상한을 확인한다.
        attempts = state["attempts"] + 1

        # 체인은 State를 모르므로 프롬프트 빈칸 8개를 모두 넘긴다.
        # 첫 초안에는 feedback이 None이라 "없음"을 넣는다.
        result = await draft_chain.ainvoke({
            "instructions": state["instructions"],
            "context": state["context"],
            "sender_name": state["sender_name"],
            "sender_relationship": state["sender_relationship"],
            "subject": state["subject"],
            "content": state["content"],
            "key_point": state["key_point"],
            "feedback": state["feedback"] or "없음",
        })

        # 노드는 바꾼 칸(draft, attempts)만 돌려준다. 나머지 State는 LangGraph가 그대로 유지한다.
        print(f"[draft] {attempts}번째 초안 작성")

        return {"draft": result, "attempts": attempts}

    # 품질 검토
    # 검토 기준으로 초안을 판정하고, 결과를 State에 남긴다.
    # 라우팅 함수가 passed와 attempts를 보고 END로 갈지, draft로 돌아가 다시 쓸지 정한다.
    async def review(state: ReplyState) -> dict:
        draft_result = state["draft"]
        assert draft_result is not None

        # 체인은 State를 모르므로 review_prompt 빈칸 6개를 모두 넘긴다.
        # 초안은 본문과 확인 필요 항목만 보여 준다.
        result = await review_chain.ainvoke({
            "context": state["context"],
            "subject": state["subject"],
            "content": state["content"],
            "key_point": state["key_point"],
            "draft_content": draft_result.content,
            "needs_confirmation": draft_result.needs_confirmation
        })

        # 결과가 ReplyReview 양식인지 확인한다.
        if not isinstance(result, ReplyReview):
            raise TypeError(f"예상하지 못한 결과 타입: {type(result)}")

        # 실습 확인 기준 : 터미널에 검토 판정과 이유를 찍는다.
        print(f"[review] 통과={result.passed}, 이유={result.reason}")

        # 판정 결과를 State 칸에 맞춰 돌려준다. reason은 다음 draft가 볼 feedback이 된다.
        return {"passed": result.passed, "feedback": result.reason}


    def router_after_review(state: ReplyState) -> str:
        if state["passed"] or state["attempts"] >= MAX_ATTEMPTS:
            return END

        return "draft"

    # 조립
    builder = StateGraph(ReplyState)

    # 노드 등록
    builder.add_node("retrieve", retrieve)
    builder.add_node("draft", draft)
    builder.add_node("review", review)

    # 일반 엣지
    builder.add_edge(START, "retrieve")
    builder.add_edge("retrieve", "draft")
    builder.add_edge("draft", "review")

    # 조건부 엣지
    builder.add_conditional_edges("review", router_after_review, ["draft", END])

    return builder.compile()
