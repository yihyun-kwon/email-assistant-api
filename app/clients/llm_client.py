import openai

import time
import asyncio

from app.core.config import Settings
from app.core.exceptions import AiRequestError
from app.schemas.reply_draft import ReplyDraft

# 1. OpenAI를 왔다 갔다 하는 클라이언트 클래스 정의
class OpenAiLlmClient:

    # 생성자
    def __init__(self, settings: Settings):
        self.settings = settings
        self.model = settings.openai_model

        # 설정 파일로부터 읽어들인 API 키가 없는 경우를 대비해 if문으로 검사한다.
        # 만약 키가 없다면 FastAPI의 lifespan이 이 클래스 대신 FakeLlmClient를 만든다.
        # 그래도 lifespan을 거치지 않고 이 클래스를 직접 만드는 경우(테스트 등)에는
        # 여기서 원인을 알려 주며 멈춘다.
        if settings.openai_api_key is None:
            raise ValueError("OpenAI Key가 없어 OpenAI 클라이언트를 만들 수 없습니다.")

        # API key값 준비: SecretStr이라서 get_secret_value()로 뽑아야 함.
        api_key = settings.openai_api_key.get_secret_value()

        # 비동기 요청 처리용 클라이언트 객체 생성
        self._async_client = openai.AsyncOpenAI(
            api_key=api_key,
            timeout=settings.openai_timeout_seconds,
            max_retries=1
        )

    # 비동기 질문
    async def ask_async(self, instructions: str, sender_name: str, sender_relationship: str,
    subject: str, content: str, key_point: str) -> ReplyDraft:

        # OpenAI SDK는 템플릿이 없어 입력 문자열을 직접 만든다.
        # 비교할 수 있도록 LangChain 클라이언트의 템플릿과 같은 모양으로 맞춘다.
        question = (
            f"[받은 메일]\n보낸 사람: {sender_name}\n"
            f"나와의 관계: {sender_relationship}\n"
            f"제목: {subject}\n내용: {content}\n\n"
            f"[답장에 담을 내용]\n{key_point}"
        )

        # 요청 시작시간 기록
        start = time.perf_counter()

        # try문 내에서 OpenAI 서버로 요청 전송
        try:
            # OpenAI Responses API 호출(POST https://api.openai.com/v1/responses)
            response = await self._async_client.responses.create(
                # 모델 지정
                model=self.settings.openai_model,
                # 지시문(시스템 프롬프트) 지정
                instructions=instructions,
                # 조립한 메일 정보
                input=question,
                # 출력 토큰 상한 지정
                max_output_tokens=self.settings.openai_max_output_tokens,
                # 추론 정도 지정
                reasoning={"effort" : self.settings.openai_reasoning_effort},
                # 대화 내용 OpenAI 서버에 저장 안함
                store=False
            )
        # openai 라이브러리의 예외(401, 429, 시간 초과 등)을/를 우리 예외로 재해석해서 다시 던진다.
        # 이 때, 'from e'를 붙여서 원래 예외가 트레이스백에 함께 찍혀 원인을 찾기 쉽도록 해주자.
        except openai.OpenAIError as e:
            raise to_ai_request_error(e) from e

        # 앞서 기록한 시작시간을 전달인자로 ㅎ하여, 콘솔 출력 함수를 호출한다.
        print_usage("ask_async", response, start)

        # OpenAI 서버의 응답 문장을 반환한다
        return ReplyDraft(content=response.output_text)
    # 정리 함수
    async def close(self):
        pass

# 2. 사용량 출력 함수
def print_usage(method: str, response, start: float) -> None:
    """걸린 시간과 토큰 사용량을 콘솔에 찍는다. 비용을 확인할 때 사용한다."""

    # 요청 처리 시간 계산
    elapsed_ms = int((time.perf_counter() - start) * 1000)

    # OpenAI의 응답 객체로부터 토큰 사용량(usage)을 추출.
    usage = response.usage

    # response.usage에서 아래와 같은 정보를 확인할 수 있다.
    # - input_tokens: 입력 토큰 수
    # - output_tokens: 출력 토큰 수
    # - total_tokens: 입력/출력 토큰의 합
    # - input_tokens_details.cached_tokens: 입력 중 캐시에서 재사용한 토큰 수
    # - output_tokens_details.reasoning_tokens: 출력 중 추론에 사용한 토큰 수
    if usage is not None:
        print(f"[OpenAiLlmClient.{method}] model={response.model}, "
              f"입력 토큰={usage.input_tokens}, 출력 토큰={usage.output_tokens}, {elapsed_ms}ms")

# 3. OpenAI 예외 변환 함수
def to_ai_request_error(e: openai.OpenAIError) -> AiRequestError:

    # AuthenticationError: OpenAI 서버의 401 응답. API 키가 틀렸거나, 삭제되었거나, 빈 문자열이다.
    if isinstance(e, openai.AuthenticationError):
        return AiRequestError("OpenAI API 키가 올바르지 않습니다. OPENAI_API_KEY를 확인하세요.")

    # RateLimitError: OpenAI 서버의 429 응답. 짧은 시간에 요청을 너무 많이 보냈거나, 계정의 충전 잔액이 바닥났다.
    if isinstance(e, openai.RateLimitError):
        return AiRequestError("OpenAI 요청 한도를 넘었거나 충전 잔액이 부족합니다.")

    # APITimeoutError: 요청은 보냈지만 timeout(OPENAI_TIMEOUT_SECONDS) 안에 응답이 오지 않음.
    # APITimeoutError는 APIConnectionError의 자식 클래스라서 예외 계층 구조상 먼저 검사한다.
    if isinstance(e, openai.APITimeoutError):
        return AiRequestError("OpenAI 응답이 제한 시간 안에 오지 않았습니다.")

    # APIConnectionError: OpenAI 서버에 닿지 못함. 인터넷 연결이 끊겼거나, 방화벽·프록시가 막았다.
    # (응답 자체를 받지 못했으므로 HTTP 상태 코드가 없다)
    if isinstance(e, openai.APIConnectionError):
        return AiRequestError("OpenAI 서버에 연결할 수 없습니다.")

    # 그 밖의 오류: 400(요청 형식 오류, 없는 모델 이름 등), 403(권한 없음), 500번대(OpenAI 서버 오류) 등.
    # 메시지에 원래 예외의 내용을 함께 담는다.
    return AiRequestError(f"OpenAI 호출 실패 : {e}")


# [실행해보기]
class FakeLlmClient:

    def __init__(self, settings: Settings):
        self.delay_seconds = settings.fake_llm_delay_seconds
        self.model = "fake-llm"

    # time.sleep : 이 스레드를 멈춰 세운다. 동기 클라이언트가 응답을 기다리는 것과 같은 상황을 만든다.
    def ask(self, instructions: str, question: str) -> str:

        time.sleep(self.delay_seconds)
        return f"(가짜 응답) '{question}'에 대한 응답입니다. {self.delay_seconds}초 기다렸습니다."

    # await asyncio.sleep : 이 코루틴만 멈춘다. 기다리는 동안 이벤트 루프는 다른 요청을 처리한다.
    # 비동기 클라이언트가 응답을 기다리는 것과 같은 상황을 만든다.

    async def ask_async(self, instructions: str, sender_name: str, sender_relationship: str,
    subject: str, content: str, key_point: str) -> ReplyDraft:

        # OpenAI SDK는 템플릿이 없어 입력 문자열을 직접 만든다.
        # 비교할 수 있도록 LangChain 클라이언트의 템플릿과 같은 모양으로 맞춘다.
        question = (
            f"[받은 메일]\n보낸 사람: {sender_name}\n"
            f"나와의 관계: {sender_relationship}\n"
            f"제목: {subject}\n내용: {content}\n\n"
            f"[답장에 담을 내용]\n{key_point}"
        )

        await asyncio.sleep(self.delay_seconds)
        return ReplyDraft(content=f"(가짜 응답) '{question}'에 대한 응답입니다. {self.delay_seconds}초 기다렸습니다.")

    async def close(self) -> None:
        pass

# 타입 힌트
LlmClient = OpenAiLlmClient | FakeLlmClient
