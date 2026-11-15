from collections.abc import Mapping
from typing import Any
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import MarkdownHeaderTextSplitter
from langchain_chroma import Chroma

from langchain_core.vectorstores import VectorStoreRetriever
from app.core.config import Settings

from app.core.config import PROJECT_ROOT

RULEBOOK_PATH = PROJECT_ROOT / "data" / "satchel_co_rulebook.md"

# 규정집 MD를 조 단위로 쪼개 임베딩한 뒤 리트리버를 만든다. 서버 시작 시 한 번만 호출한다.
def build_rulebook_retriever(settings: Settings) -> VectorStoreRetriever:

    text =  RULEBOOK_PATH.read_text(encoding="utf-8")
    splitter = MarkdownHeaderTextSplitter(headers_to_split_on=[
        ("##", "chapter"),
        ("###", "article")
    ])
    docs = [doc for doc in splitter.split_text(text) if doc.metadata.get("article")]
    embeddings = OpenAIEmbeddings(
        model=settings.openai_embedding_model,
        api_key=settings.openai_api_key
    )
    vectorstore = Chroma.from_documents(
        documents=docs,
        embedding=embeddings,
        collection_name="rulebook"
    )
    return vectorstore.as_retriever(search_kwargs={"k": 2})

# 검색된 조항들을 "조 제목 + 본문" 문자열로 합친다.
# 조 번호는 metadata에만 있어 제목을 앞에 붙인다.
def format_docs(docs: list[Document]) -> str:
    return "\n\n".join(doc.metadata.get("article") + "\n" + doc.page_content
        for doc in docs
        if doc.metadata.get("article"))

# 규정 검색어 : 제목, 내용, keyPoint만 이어 붙인다. 관계와 보낸 사람은 검색을 흐리게 하므로 뺀다.
def build_search_query(data: Mapping[str, Any]) -> str:
    return "\n".join([
        data["subject"],
        data["content"],
        data["key_point"]
    ])
