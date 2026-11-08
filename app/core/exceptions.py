from fastapi.responses import JSONResponse
from fastapi import FastAPI, Request


# 메일 조회 실패 예외
class EmailNotFoundError(Exception):

    def __init__(self, email_id: int):
        super().__init__(f"해당 메일이 존재하지 않습니다. email_id={email_id}")
        self.email_id = email_id

# OpenAI 호출 실패 예외 
# 원인과 상관없이 모두 502로 응답하기에 필드를 두지 않는다.
class AiRequestError(Exception):
    pass


# 예외 처리기 등록 함수
def register_exception_handlers(app: FastAPI) -> None:
    
    # 메일 조회 실패 → 404 응답
    @app.exception_handler(EmailNotFoundError)
    def handle_email_not_found(request: Request, e: EmailNotFoundError):
        return JSONResponse(
            status_code=404,
            content={
                "code": "EMAIL_NOT_FOUND",
                "description": "메일 조회 실패",
                "detail": str(e),
            },
        )

    # OpenAI 호출 실패 → 502 응답
    @app.exception_handler(AiRequestError)
    def handle_ai_request_error(request: Request, e: AiRequestError):
        return JSONResponse(
            status_code=502,
            content={
                "code": "AI_REQUEST_FAILED",
                "description": "답장 초안 생성 실패",
                "detail": str(e),
            },
        )