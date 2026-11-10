# 비즈니스 메일 답장 초안 API 서버

받은 업무 메일을 저장해 두고, 답장에 담을 내용과 보낸 사람과의 관계를 입력하면 LLM이 원본 메일을 참고해 답장 본문을 작성해 주는 FastAPI 서버입니다. LLM 호출은 LangChain으로 구성했습니다.

## 주요 기능

- **메일 등록:** 발신자 이름, 제목, 내용을 입력해 메일을 저장한다.
- **메일 조회:** 메일 번호로 저장된 메일을 조회한다.
- **답장 초안 생성:** 저장된 메일과 답장에 담을 내용을 바탕으로 LLM이 관계(상사, 동료, 거래처, 고객)에 맞는 말투로 답장 본문을 작성한다. 답장에 반영한 규정 조항(추가 예정)과, 입력한 내용만으로 답할 수 없어 확인이 필요한 질문을 함께 돌려준다.

## API

| 메서드 | 주소 | 핸들러 | 설명 | 응답 |
|---|---|---|---|---|
| POST | `/api/emails` | `def` | 메일 등록 | 201 등록 성공, 422 잘못된 값 |
| GET | `/api/emails/{email_id}` | `def` | 메일 하나 조회 | 200 조회 성공, 404 없는 메일, 422 잘못된 번호 |
| POST | `/api/emails/{email_id}/reply` | `async def` | 답장 초안 생성 | 200 생성 성공, 404 없는 메일, 422 잘못된 값, 502 OpenAI 호출 실패 |

JSON 키는 camelCase로 주고받는다.

### 메일 등록 요청 예시

```json
{
  "senderName": "김민수",
  "subject": "창립기념 행사 참석 인원 확인",
  "content": "참석 인원이 287명으로 집계되었는데 맞는지 확인 부탁드립니다."
}
```

### 답장 초안 요청 예시

```json
{
  "keyPoint": "287명이 맞고, 낮 12시 전에 정리해서 보내겠다",
  "senderRelationship": "상사"
}
```

`senderRelationship`은 `상사`, `동료`, `거래처`, `고객` 중 하나다. 목록에 없는 값이면 422로 응답한다.

### 답장 초안 응답 예시

```json
{
  "subject": "RE: 창립기념 행사 참석 인원 확인",
  "content": "안녕하세요. 김민수님, 경영지원팀 홍길동입니다.\n\n(LLM이 작성한 본문)\n\n경영지원팀 홍길동 사원 드림",
  "model": "gpt-6-luna",
  "citedRules": [],
  "needsConfirmation": []
}
```

- `citedRules`: 답장의 근거로 사용한 사내 규정 조항 번호 (규정집 연결 전으로 현재는 항상 빈 목록)
- `needsConfirmation`: 답장에 담을 내용만으로 답할 수 없어 사용자가 확인해야 할 질문

## 설계 기준

- 수신자는 한 명으로 가정해 수신자 정보를 저장하지 않는다.
- 데이터는 DB 대신 메모리(딕셔너리)에 저장하므로 서버를 다시 시작하면 처음 상태로 돌아간다.
- 서버가 시작할 때 더미 메일 10개를 저장하므로, 새로 등록한 메일은 11번부터 시작한다.
- 답장 초안은 응답으로만 보내고 저장하지 않는다.
- LLM을 기다리는 동안 다른 요청을 처리할 수 있도록 답장 API는 `async def`와 `await`로 작성한다.
- 답장 제목은 LLM에 맡기지 않고 `RE: ` + 원본 제목으로 고정한다.
- 인사말과 서명은 형식이 항상 같으므로 코드가 붙이고, LLM에는 본문만 쓰게 한다. 서명 이름은 `.env`의 `REPLIER_NAME`으로 바꿀 수 있다.
- LLM 응답은 구조화 출력(`ReplyDraft`)으로 받아 본문, 근거 조항, 확인 필요 사항을 칸별로 꺼낸다.
- 입력한 내용만으로 답할 수 없는 질문은 지어내지 않고 `needsConfirmation`으로 넘긴다.
- LLM 호출은 기본으로 LangChain(`ChatOpenAI`)을 거친다. `.env`에 `LLM_PROVIDER=openai`를 적으면 OpenAI SDK 직접 호출로 바꿔 비교할 수 있다.

## 프로젝트 구조

```text
app/
├── main.py                     # 앱 생성, 라우터와 예외 처리기 등록
├── dependencies.py             # 의존성 함수
├── clients/
│   ├── llm_client.py           # OpenAI SDK 직접 호출, 가짜 LLM 클라이언트
│   └── langchain_client.py     # LangChain(ChatOpenAI) 클라이언트 (기본)
├── core/
│   ├── config.py               # 환경 변수와 .env 설정
│   └── exceptions.py           # 예외와 예외 처리기
├── domain/
│   └── email.py                # 메일 엔티티
├── repositories/
│   └── email_repository.py     # 메모리 저장소, 더미 메일
├── routers/
│   └── email_router.py         # 메일, 답장 API 핸들러
├── schemas/
│   ├── base.py                 # camelCase 설정 부모 DTO
│   ├── email.py                # 요청, 응답 DTO
│   └── reply_draft.py          # LLM 구조화 출력 양식
└── services/
    ├── email_service.py        # 메일 등록, 조회 로직
    └── reply_service.py        # 답장 초안 생성 로직
```

## 실행 방법

Antigravity IDE에서 프로젝트 폴더를 열고 진행한다.

1. Antigravity IDE 내에서 터미널(Ctrl + Shift + `)을 연 후 라이브러리를 설치한다.

   ```bash
   uv sync
   ```

2. 상태 표시줄의 파이썬 인터프리터가 이 프로젝트의 `.venv`를 가리키는지 확인한다.

3. 탐색기에서 프로젝트 폴더 바로 아래에 `.env` 파일을 새로 만들고 `.env.example`의 내용을 복사 붙여넣기 한다. 
그런 다음 `# 1. OpenAI Platform 관련 설정` 항목의 값을 채운다. 예시는 다음과 같다.

   ```ini
   OPENAI_MODEL=gpt-6-luna
   OPENAI_REASONING_EFFORT=none
   OPENAI_MAX_OUTPUT_TOKENS=300
   OPENAI_TIMEOUT_SECONDS=30
   ```
LLM 호출 방식(`LLM_PROVIDER`)과 서명 이름(`REPLIER_NAME`)은 기본값이 있어 채우지 않아도 된다.

4. API 키는 환경 변수 `OPENAI_API_KEY`에 등록되어 있다고 가정한다.  
(만약 키가 없거나 `FAKE_LLM=true`이면 OpenAI 대신 가짜 응답을 사용한다.)

5. 터미널에서 서버를 실행한다.

   ```bash
   uv run fastapi dev
   ```

6. 터미널에 표시된 주소 뒤에 `/docs`를 붙여 브라우저에서 열고 API를 확인한다. 
(기본 주소 : <http://127.0.0.1:8000/docs>)


