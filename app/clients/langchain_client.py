import openai

from langchain_core.prompts.chat import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from app.clients.llm_client import to_ai_request_error
from app.core.config import Settings
from app.schemas.reply_draft import ReplyDraft

# LangChain(ChatOpenAI) 클라이언트
class LangChainLlmClient:

    def __init__(self, settings: Settings):
        self.model = settings.openai_model

        # LangChain의 OpenAI 채팅 모델 객체
        self.llm = ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            timeout=settings.openai_timeout_seconds,
            max_tokens=settings.openai_max_output_tokens,
            max_retries=1,
        )

        # 프롬프트 템플릿 : 요청마다 지시문과 질문을 빈칸에 채운다.
        prompt = ChatPromptTemplate.from_messages([
            ("system", "{instructions}"),
            ("human", "{question}")
        ])

        # 체인 : 템플릿 → 모델 → ReplyDraft 양식으로 받기 (구조화 출력)
        self.chain = prompt | self.llm.with_structured_output(ReplyDraft)

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