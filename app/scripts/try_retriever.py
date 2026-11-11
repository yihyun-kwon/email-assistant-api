"""규정집 검색 검사용 스크립트

서버를 띄우지 않고 리트리버가 기대한 조항을 찾는지 확인한다.
규정집을 고쳤거나, k·임베딩 모델을 바꿨거나, 답장이 이상해 검색 탓인지 볼 때 실행한다.

실행 : uv run python -m app.scripts.try_retriever
"""

from app.core.config import get_settings
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import MarkdownHeaderTextSplitter
from app.core.config import PROJECT_ROOT

# 서버와 같은 방식으로 설정을 읽는다.
settings = get_settings()


# ===== ① 규정집 읽기 =====
RULEBOOK_PATH = PROJECT_ROOT / "data" / "satchel_co_rulebook.md"
text = RULEBOOK_PATH.read_text(encoding="utf-8")

# ===== ② 조항 단위로 나누기 =====
# 장 제목과 조 제목을 기준으로 자르고, 각 제목을 metadata에 붙인다.
splitter = MarkdownHeaderTextSplitter(
    headers_to_split_on=[
        ("##", "chapter"),
        ("###", "article")
    ]
)

all_docs = splitter.split_text(text)
docs = [doc for doc in all_docs if doc.metadata.get("article")]

# ===== ③ 임베딩 모델 준비 =====
embeddings = OpenAIEmbeddings(
    model =settings.openai_embedding_model,
    api_key=settings.openai_api_key,
)

# ===== ④ 벡터 DB에 저장 =====
# 조각들을 임베딩으로 바꿔 Chroma에 저장한다.
vectorstore = Chroma.from_documents(
    documents=docs,
    embedding=embeddings,
    collection_name="rulebook",
)

# ===== ⑤ 리트리버 만들기 =====
# 검색어를 받아 가장 비슷한 조각 k개를 돌려주는 부품
retriever = vectorstore.as_retriever(search_kwargs={"k": 2})

# ===== ⑥ 검색해 보기 =====
# 검색어마다 기대하는 조항 : 제15조, 제13조, 제24조, 제21조
queries = [
    "출장 경비 영수증 누락",
    "견적서 수량 수정",
    "고객 응대 매뉴얼 검토",
    "담당이 아닌 메일",
]

for query in queries:
    results = retriever.invoke(query)

    print(f"\n[검색어] {query}")
    for doc in results:
        print("   -", doc.metadata.get("article"))
