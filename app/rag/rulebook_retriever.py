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
