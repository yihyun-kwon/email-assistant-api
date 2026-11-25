from dotenv import load_dotenv
load_dotenv()

import asyncio, json
from langsmith import Client, aevaluate

from app.services.reply_service import INSTRUCTIONS
from app.rag.rulebook_retriever import build_rulebook_retriever
from app.clients.langchain_client import LangChainLlmClient
from app.core.config import get_settings

DATASET_NAME = "email-reply-goldset"

# GoldSet에 없는 값
FAKE_SENDER_NAME = "김민수"
FAKE_SUBJECT = "업무 문의"

settings = get_settings()
retriever = build_rulebook_retriever(settings)
llm_client = LangChainLlmClient(settings, retriever)

# 평가 대상
async def target(inputs: dict) -> dict:
    draft = await llm_client.ask_async(
        instructions=INSTRUCTIONS,
        sender_name=FAKE_SENDER_NAME,
        sender_relationship=inputs["relationship"],
        subject=FAKE_SUBJECT,
        content=inputs["content"],
        key_point=inputs["key_point"],
    )
    return {
        "content": draft.content,
        "cited_rules": draft.cited_rules,
        "needs_confirmation": draft.needs_confirmation
    }

# GoldSet 읽기
with open("data/goldset.json", encoding="utf-8") as f:
    goldset = json.load(f)

client = Client()
if not client.has_dataset(dataset_name=DATASET_NAME):
    dataset = client.create_dataset(dataset_name=DATASET_NAME)
    client.create_examples(
        dataset_id=dataset.id,
        examples=[
            {
                "inputs": {"content": g["content"], "key_point": g["key_point"], "relationship": g["relationship"]},
                "outputs": {"source": g["source"], "answer": g["answer"]}
            }
            for g in goldset
        ]
    )

def cited_rules_hit(inputs: dict, outputs: dict, reference_outputs: dict) -> dict:
    hit = set(reference_outputs["source"]) <= set(outputs["cited_rules"])
    return {"key": "cited_rules_hit", "score": 1 if hit else 0}

async def main() -> None:
    await aevaluate(
        target,
        data=DATASET_NAME,
        evaluators=[cited_rules_hit],
        experiment_prefix="reply-graph",
    )

if __name__ == "__main__":
    asyncio.run(main())
