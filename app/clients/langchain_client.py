from app.graphs.reply_graph import build_reply_graph
import openai
from langchain_openai import ChatOpenAI

from langchain_core.runnables import RunnablePassthrough
from langchain_core.vectorstores import VectorStoreRetriever
from langchain_core.prompts.chat import ChatPromptTemplate

from app.clients.llm_client import to_ai_request_error
from app.core.config import Settings
from app.schemas.reply_draft import ReplyDraft
from app.rag.rulebook_retriever import build_search_query, format_docs


# LangChain(ChatOpenAI) 클라이언트
class LangChainLlmClient:

    def __init__(self, settings: Settings, retriever: VectorStoreRetriever):
        self.model = settings.openai_model
        self.retriever = retriever

        # LangChain의 OpenAI 채팅 모델 객체
        self.llm = ChatOpenAI(
            # 사용할 모델
            model=settings.openai_model,
            # API 키
            api_key=settings.openai_api_key,
            # 응답 대기 최대 시간(초)
            timeout=settings.openai_timeout_seconds,
            # 출력 토큰 상한 (추론 토큰 포함)
            max_tokens=settings.openai_max_output_tokens,
            # Responses API로 요청
            use_responses_api=True,
            # 추론 정도
            reasoning={"effort": settings.openai_reasoning_effort},
            # 대화 내용을 OpenAI 서버에 저장하지 않는다.
            store=False,
            # 실패 시 재시도 횟수
            max_retries=1,
        )

        # 프롬프트 템플릿
        prompt = ChatPromptTemplate.from_messages([
            ("system", "{instructions}\n\n[참고 규정]\n{context}"),
            ("human",
            "[받은 메일]\n보낸 사람: {sender_name}\n"
            "나와의 관계: {sender_relationship}\n"
            "제목: {subject}\n내용: {content}\n\n"
            "[답장에 담을 내용]\n{key_point}")
        ])

        # 체인 : 템플릿 → 모델 → ReplyDraft 양식으로 받기 (구조화 출력)
        self.chain = (
            RunnablePassthrough.assign(
                context= build_search_query | self.retriever | format_docs
            )
            | prompt
            | self.llm.with_structured_output(ReplyDraft)
        )
        # 검토 루프 그래프 : 검색 → 초안 → 검토
        self.graph = build_reply_graph(self.llm, self.retriever)

    # 비동기 질문
    async def ask_async(self, instructions: str, sender_name: str, sender_relationship: str,
    subject: str, content: str, key_point: str) -> ReplyDraft:

        # 그래프의 처음 State를 넘긴다.

        try:
            state = await self.graph.ainvoke({
                "instructions": instructions,
                "sender_name":  sender_name,
                "sender_relationship": sender_relationship,
                "subject": subject,
                "content": content,
                "key_point": key_point,
                "context": "",
                "attempts": 0,
                "passed": False,
                "draft": None,
                "feedback": None
            })
        # 기존 변환 함수를 재사용하여 502로 응답하게 한다.
        except openai.OpenAIError as e:
            raise to_ai_request_error(e) from e

        # 그래프 결과(State)에서 최종 초안을 꺼낸다.
        result = state["draft"]

        # 결과가 ReplyDraft 양식인지 확인한다.
        if not isinstance(result, ReplyDraft):
            raise TypeError(f"예상하지 못한 결과 타입: {type(result)}")
        return result

    # 서버 종료 시 lifespan이 호출한다.
    async def close(self) -> None:
        pass
