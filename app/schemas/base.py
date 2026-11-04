from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


# 파이썬의 snake_case 필드를 JSON에서 camelCase로 주고받는 DTO 부모 클래스
class CamelModel(BaseModel):

    model_config = ConfigDict(
        # snake_case 필드에 camelCase 별칭을 자동으로 붙인다.
        alias_generator=to_camel,
        # snake_case 이름으로도 값을 받을 수 있게 한다.
        populate_by_name=True,
    )
