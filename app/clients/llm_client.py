import openai

import time
import asyncio

from app.core.config import Settings
from app.core.exceptions import AiRequestError

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

        # 동기 클라이언트와 비동기 클라이언트를 동일한 설정으로 만든다.
        # (기존 Spring Boot에서는 LLM 서버를 다녀오기 위해 RestClient를 만들었다)
        # - api_key : SecretStr에서 실제 키 문자열을 꺼내 전달한다
        # - timeout : 응답을 기다리는 최대 시간(초)
        # - max_retries : 연결 실패나 서버 오류일 때 다시 시도할 횟수

        # 동기 요청 처리용 클라이언트 객체 생성
        self._client = openai.OpenAI(
            api_key=api_key,
            timeout=settings.openai_timeout_seconds,
            max_retries=1
        )
        # 비동기 요청 처리용 클라이언트 객체 생성
        self._async_client = openai.AsyncOpenAI(
            api_key=api_key,
            timeout=settings.openai_timeout_seconds,
            max_retries=1
        )

    # 1) 동기 질문
    # 응답이 올 때까지 해당 라인에서 스레드가 멈춰있게 된다.
    # 따라서 그동안 이 스레드는 다른 일을 할 수 없다.
    # instructions => 시스템 프롬프트, questions => 유저 프롬프트
    def ask(self, instructions: str, questions: str) -> str:

        # 요청 시작시간 기록
        start = time.perf_counter()

        # try문 내에서 OpenAI 서버로 요청 전송
        try:
            # OpenAI Responses API 호출(POST https://api.openai.com/v1/responses)
            response = self._client.responses.create(
                # 모델 지정
                model=self.settings.openai_model,
                # 지시문(시스템 프롬프트) 지정
                instructions=instructions,
                # 질문(손님의 채팅) 지정
                input=questions,
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
        print_usage("ask", response, start)

        # OpenAI 서버의 응답 문장을 반환한다
        return response.output_text

    # 2) 비동기 질문
    async def ask_async(self, instructions: str, questions: str) -> str:

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
                # 질문(손님의 채팅) 지정
                input=questions,
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
        return response.output_text
    # 3) 정리 함수
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
    """
    openai 라이브러리의 예외를 우리 예외로 바꾼다. (Spring Boot에서 HTTP 상태 코드를 보고 우리 예외로 바꿨던 일)

    Args:
        e (openai.OpenAIError): OpenAI 호출 중 발생한 예외

    Returns:
        AiRequestError: 대신 던질 예외. 던지는 것은 호출한 쪽(raise ... from e)이다.
    """

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
    """
    OpenAI를 호출하지 않는 가짜 클라이언트. 키가 없거나 FAKE_LLM=true일 때 사용한다.
    LLM이 응답하는 데 걸리는 시간만 흉내 내고, 정해진 문장을 반환한다.
    """

    def __init__(self, settings: Settings):
        self.delay_seconds = settings.fake_llm_delay_seconds
        self.model = "fake-llm"

    # time.sleep : 이 스레드를 멈춰 세운다. 동기 클라이언트가 응답을 기다리는 것과 같은 상황을 만든다.
    def ask(self, instructions: str, question: str) -> str:
        time.sleep(self.delay_seconds)
        return f"(가짜 응답) '{question}'에 대한 응답입니다. {self.delay_seconds}초 기다렸습니다."

    # await asyncio.sleep : 이 코루틴만 멈춘다. 기다리는 동안 이벤트 루프는 다른 요청을 처리한다.
    # 비동기 클라이언트가 응답을 기다리는 것과 같은 상황을 만든다.
    async def ask_async(self, instructions: str, question: str) -> str:
        await asyncio.sleep(self.delay_seconds)
        return f"(가짜 응답) '{question}'에 대한 응답입니다. {self.delay_seconds}초 기다렸습니다."

    async def close(self) -> None:
        pass

# 타입 힌트
LlmClient = OpenAiLlmClient | FakeLlmClient
