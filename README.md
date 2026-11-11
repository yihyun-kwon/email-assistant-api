# 비즈니스 메일 답장 초안 API 서버

업무 메일 답장 초안을 AI가 작성하는 FastAPI 서버입니다.

답장에 담을 내용과 보낸 사람과의 관계를 입력하면 원본 메일과 사내 규정집을 참고해 본문을 작성합니다. 

LangChain과 Chroma 기반 RAG로 구성했습니다.
## 주요 기능

- **메일 등록:** 발신자 이름, 제목, 내용을 입력해 메일을 저장한다.
- **메일 조회:** 메일 번호로 저장된 메일을 조회한다.
- **답장 초안 생성:** 저장된 메일과 답장에 담을 내용을 바탕으로 LLM이 관계(상사, 동료, 거래처, 고객)에 맞는 말투로 답장 본문을 작성한다. 
관련 사내 규정을 검색해 근거로 반영하고, 반영한 규정 조항 번호와 입력한 내용만으로 답할 수 없어 확인이 필요한 질문을 함께 돌려준다.

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
  "content": "안녕하세요, 김민수님. 경영지원팀 홍길동입니다.\n\n(LLM이 작성한 본문)\n\n경영지원팀 홍길동 사원 드림",
  "model": "gpt-6-luna",
  "citedRules": ["제6조"],
  "needsConfirmation": []
}
```

- `citedRules`: 답장에 실제로 반영한 사내 규정 조항 번호. 관련 규정이 없으면 빈 목록
- `needsConfirmation`: 답장에 담을 내용만으로 답할 수 없어 사용자가 확인해야 할 질문

## 설계 기준

**데이터**
- 수신자는 한 명으로 가정해 수신자 정보를 저장하지 않는다.
- DB 대신 메모리(딕셔너리)에 저장한다. 서버를 다시 시작하면 더미 메일 10개만 남고, 새 메일은 11번부터 번호가 붙는다.
- 답장 초안은 응답으로만 보내고 저장하지 않는다.

**답장 생성**
- 답장 API는 `async def`와 `await`로 작성해 LLM을 기다리는 동안 다른 요청을 처리한다.
- 제목은 `RE: ` + 원본 제목, 인사말과 서명은 코드가 붙인다. LLM에는 본문만 맡긴다. (서명 이름은 `REPLIER_NAME`)
- LLM 응답은 구조화 출력(`ReplyDraft`)으로 받아 본문, 근거 조항, 확인 필요 질문을 나눠 돌려준다. 
- 입력만으로 답할 수 없는 질문은 지어내지 않고 `needsConfirmation`에 담는다.

**LLM과 RAG**
- LLM 호출은 LangChain(`ChatOpenAI`)을 거친다. `LLM_PROVIDER=openai`로 바꾸면 OpenAI SDK 직접 호출과 비교할 수 있다.
- 사내 규정집(`data/satchel_co_rulebook.md`)을 조 단위로 임베딩해 Chroma에 넣고, 
요청마다 관련 조항 2개를 검색해 프롬프트의 `[참고 규정]`에 넣는다. 
LLM은 참고 규정만 근거로 쓰고, 관련 없는 조항은 무시한다.
- Chroma는 서버 시작 시 메모리에 한 번 만든다. 규정집이 25개 조항으로 작아 디스크에 남길 필요가 없다.

## 프로젝트 구조

```text
app/
├── main.py                     # 앱 생성, 라우터와 예외 처리기 등록, 시작 시 LLM 클라이언트와 리트리버 생성
├── dependencies.py             # 의존성 함수
├── clients/
│   ├── llm_client.py           # OpenAI SDK 직접 호출, 가짜 LLM 클라이언트
│   └── langchain_client.py     # LangChain(ChatOpenAI) 클라이언트 + RAG 체인 (기본)
├── core/
│   ├── config.py               # 환경 변수와 .env 설정
│   └── exceptions.py           # 예외와 예외 처리기
├── domain/
│   └── email.py                # 메일 엔티티
├── rag/
│   └── rulebook_retriever.py   # 규정집 읽기 → 조 단위 분할 → 임베딩 → Chroma → 리트리버
├── repositories/
│   └── email_repository.py     # 메모리 저장소, 더미 메일
├── routers/
│   └── email_router.py         # 메일, 답장 API 핸들러
├── schemas/
│   ├── base.py                 # camelCase 설정 부모 DTO
│   ├── email.py                # 요청, 응답 DTO
│   └── reply_draft.py          # LLM 구조화 출력 양식
├── scripts/
│   └── try_retriever.py        # 규정집 검색 검사용 스크립트 (서버와 무관)
└── services/
    ├── email_service.py        # 메일 등록, 조회 로직
    └── reply_service.py        # 답장 초안 생성 로직, LLM 지시문
data/
├── satchel_co_rulebook.md      # 가상 회사 Satchel & Co. 사내 규정집 (RAG 근거 문서)
└── satchel_co_rulebook.pdf     # 같은 내용의 PDF (열람용)
```

## 실행 방법

Antigravity IDE에서 프로젝트 폴더를 열고 진행한다.

1. 터미널(Ctrl + Shift + `)을 열고 라이브러리를 설치한다.

   ```bash
   uv sync
   ```

2. 상태 표시줄의 파이썬 인터프리터가 이 프로젝트의 `.venv`를 가리키는지 확인한다.

3. 프로젝트 폴더 바로 아래에 `.env` 파일을 만들고 `.env.example`의 내용을 복사한 뒤, `# 1. OpenAI Platform 관련 설정` 항목의 값을 채운다.

   ```ini
   OPENAI_MODEL=gpt-6-luna
   OPENAI_EMBEDDING_MODEL=text-embedding-3-large
   OPENAI_REASONING_EFFORT=none
   OPENAI_MAX_OUTPUT_TOKENS=300
   OPENAI_TIMEOUT_SECONDS=30
   ```

   나머지 항목(`LLM_PROVIDER`, `REPLIER_NAME` 등)은 기본값이 있어 그대로 둬도 된다.

4. API 키는 환경 변수 `OPENAI_API_KEY`에 등록되어 있어야 한다. 
키가 없거나 `FAKE_LLM=true`이면 OpenAI 대신 가짜 응답을 사용한다.

5. 서버를 실행한다.

   ```bash
   uv run fastapi dev
   ```

   시작 로그에 `[lifespan] LangChain 클라이언트를 사용한다 (model=..., embedding=...)`가 보이면 규정집 임베딩까지 끝난 것이다.

6. 브라우저에서 <http://127.0.0.1:8000/docs>를 열어 API를 확인한다.

## 규정집 검색 확인

서버를 띄우지 않고 리트리버가 기대한 조항을 찾는지 확인할 수 있다. 규정집을 고치거나 검색 설정을 바꿨을 때 실행한다.

```bash
uv run python -m app.scripts.try_retriever
```

검색어 4개에 대해 각각 가장 가까운 조항 2개를 출력한다. (예: "출장 경비 영수증 누락" → 제15조, 제14조)
