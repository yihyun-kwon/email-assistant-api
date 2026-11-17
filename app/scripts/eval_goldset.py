from dotenv import load_dotenv
load_dotenv()

import asyncio, json
from langsmith import Client, aevaluate
from pydantic import BaseModel, Field

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

def cited_rules_hit(inputs: dict, outputs: dict, reference_outputs: dict) -> bool:
    return set(reference_outputs["source"]) <= set(outputs["cited_rules"])

class Judgement(BaseModel):
    correct: bool = Field(description="응답이 [채점 기준]을 모두 지켰다면 true")
    reason: str = Field(description="판단 이유 한 문장")

    judge = llm_client.llm.with_structured_output(Judgement)

    def correctness(inputs: dict, outputs: dict, reference_outputs: dict) -> dict:
        judgement = judge.invoke(
            "너는 업무 메일 답장을 채점한다. 말투와 길이는 채점하지 않는다 [채점 기준]을 지켰는지만 본다. \n\n"
        )
