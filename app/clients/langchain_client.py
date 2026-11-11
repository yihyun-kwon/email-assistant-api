from langchain_core.documents import Document
from langchain_core.runnables import RunnablePassthrough
from langchain_core.vectorstores import VectorStoreRetriever
import openai

from langchain_core.prompts.chat import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from app.clients.llm_client import to_ai_request_error
from app.core.config import Settings
from app.schemas.reply_draft import ReplyDraft

# 검색된 조항들을 "조 제목 + 본문" 문자열로 합친다.
# 조 번호는 metadata에만 있어 제목을 앞에 붙인다.
def format_docs(docs: list[Document]) -> str:
    return "\n\n".join(doc.metadata.get("article") + "\n" + doc.page_content
        for doc in docs
        if doc.metadata.get("article"))

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

        # 프롬프트 템플릿 : 요청마다 지시문과 질문을 빈칸에 채운다.
        prompt = ChatPromptTemplate.from_messages([
            ("system", "{instructions}\n\n[참고 규정]\n{context}"),
            ("human", "{question}")
        ])

        # 체인 : 템플릿 → 모델 → ReplyDraft 양식으로 받기 (구조화 출력)
        self.chain = (
            RunnablePassthrough.assign(
                context=(lambda x: x["question"]) | self.retriever | format_docs
            )
            | prompt
            | self.llm.with_structured_output(ReplyDraft)
        )

    # 비동기 질문
    async def ask_async(self, instructions: str, question: str) -> ReplyDraft:

        # 템플릿의 빈칸 이름을 키로 값을 넘긴다.
        try:
            result = await self.chain.ainvoke({
                "instructions": instructions,
                "question": question,
            })
        # 기존 변환 함수를 재사용하여 502로 응답하게 한다.
        except openai.OpenAIError as e:
            raise to_ai_request_error(e) from e

        # 결과가 ReplyDraft 양식인지 확인한다.
        if not isinstance(result, ReplyDraft):
            raise TypeError(f"예상하지 못한 결과 타입: {type(result)}")
        return result

    # 서버 종료 시 lifespan이 호출한다.
    async def close(self) -> None:
        pass
