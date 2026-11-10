
#설정값 (Spring의 application.yaml + @ConfigurationProperties 역할)


from pathlib import Path
from typing import Literal
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, SecretStr


# 1. 설정 파일(.env) 경로 잡기
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# 2. 설정 클래스 생성
# BaseSettings는 DTO에서 사용한 BaseModel을 상속받아 만든 클래스다.
# 타입 검사는 BaseModel과 동일하며, 환경 변수와 .env 파일에서 값을 읽는 기능이 더해진
# BaseModel의 하위 클래스라고 보면 된다. (Settings는 다시 이 BaseSettings를 상속받는다)
class Settings(BaseSettings):

    # DTO의 model_config와 동일하게, 클래스 변수 model_config에 설정을 적는다.
    model_config = SettingsConfigDict(
        # .env 파일의 위치와 인코딩
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        # 이 클래스에 없는 환경 변수는 무시한다
        extra="ignore",
    )

    # OpenAi API key값: Pydantic에서 제공해주는 SecretStr 타입을 사용한다.
    # (시스템 환경변수로부터 읽어와야 한다)
    # 이는 비밀번호, API 키, 토큰 등 민감한 문자열 데이터를 안전하게 처리하기 위해 사용하는 데이터 타입이다.
    # print()를 하거나 로그를 남길 때 '**********'로 마스킹되어 찍힌다.
    # 따라서 코드 내에서 실제 값은 get_secret_value()를 호출해 사용해야 한다.
    # 기본값을 None으로 설정해서 OpenAI API 키가 없거나 인식되지 않더라도 서버는 실행된다.
    # 그때는 가짜 LLM 클라이언트를 사용한다.
    openai_api_key: SecretStr | None = None

    # 사용할 모델
    openai_model: str = "gpt-6-luna"

    # 추론 정도 : 사용 가능한 값들을 Literal로 정해 두면 .env에 오타(nnone 등)를 적었을 때 서버가 시작하면서 알려 준다.
    # none은 추론 없이 바로 응답한다. 질문에 답하는 정도의 일에는 충분하고 응답도 빠르다.
    openai_reasoning_effort: Literal["none", "minimal", "low", "medium", "high", "xhigh"] = "none"

    # 출력 토큰 상한 : 상한을 넘으면 응답이 중간에 끊긴다. 0보다 커야 한다.
    openai_max_output_tokens: int = Field(default=300, gt=0)

    # OpenAI의 응답을 기다리는 최대 시간(초). 0보다 커야 한다.
    openai_timeout_seconds: float = Field(default=30.0, gt=0)

    # 가짜 LLM : true면 키가 있어도 OpenAI를 호출하지 않는다. 비용 없이 시험하거나 성능을 잴 때 사용한다.
    fake_llm: bool = False

    # 가짜 LLM이 응답하기 전에 기다리는 시간(초). 실제 LLM의 응답 시간을 흉내 낸다. 0 이상이어야 한다.
    fake_llm_delay_seconds: float = Field(default=3.0, ge=0)

    # 실험용 : def 핸들러를 실행할 스레드의 수. None이면 FastAPI의 기본값(40개)을 그대로 사용한다.
    # 1로 줄이면 def 핸들러가 한 번에 하나씩만 실행되는 것을 눈으로 확인할 수 있다(routers/ai_router.py의 실험 2).
    thread_pool_size: int | None = Field(default=None, ge=1)

    # 답장 서명에 들어갈 이름. .env에 없으면 기본값을 사용한다.
    replier_name: str = "홍길동"

    # LLM 호출 방식 : openai(OpenAI SDK 직접) 또는 langchain(LangChain 경유). 둘 다 같은 OpenAI 모델을 호출한다.
    # 이 값은 수정하지 않고, LangChain을 쓰려면 .env에 LLM_PROVIDER=langchain을 적은 뒤 서버를 다시 시작한다.
    llm_provider: Literal["openai", "langchain"] = "openai"



# 3. 설정 객체 반환함수 정의 (feat. @lru_cache)

# FastAPI 프로젝트에서 functools(파이썬 표준 라이브러리)의 @lru_cache 데코레이터는 주로 환경 설정(.env)이나
# 무거운 객체(DB 연결 클라이언트, ML 모델 등)를 요청마다 새로 로드하지 않고,
# 애플리케이션 전체에 딱 한 번만 생성하여 재사용(싱글톤 패턴 효과)하는 목적으로 사용한다.
# 여기서는 Settings()를 만들 때마다 .env 파일을 다시 읽지 않도록(무거울 수 있는 IO 작업),
# 처음 만든 객체를 기억해 두고 계속 반환한다. (Spring의 싱글톤 빈과 같은 역할)
@lru_cache
def get_settings() -> Settings:
    return Settings()

# 확인 : 프로젝트 폴더의 터미널에서 아래를 실행하면 읽어 들인 설정이 찍힌다. 키는 별표로 가려진다.
#   uv run python -c "from app.core.config import get_settings; print(get_settings())"
# 출력 예시
#   openai_api_key=SecretStr('**********') openai_model='gpt-6-luna' openai_reasoning_effort='none' ...
