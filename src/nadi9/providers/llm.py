from __future__ import annotations
from langchain_groq import ChatGroq
import json
import os
from typing import Any

from nadi9.providers.base import LLMProvider
from nadi9.translation.prompts import HYPOTHESIS_RULES, TRANSLATOR_RULES, VERIFIER_RULES


class OpenAIProvider(LLMProvider):
    name = "groq"

    def __init__(self, model: str):
        self.model = model

    def generate(self, purpose: str, payload: dict[str, Any]) -> dict[str, Any]:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY missing; use --mode mock")
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import HumanMessage, SystemMessage

        rules = {
            "hypotheses": HYPOTHESIS_RULES,
            "translate": TRANSLATOR_RULES,
            "verify": VERIFIER_RULES,
        }.get(purpose, TRANSLATOR_RULES)
        llm = ChatGroq(model="meta-llama/llama-prompt-guard-2-22m", temperature=0)
        msg = llm.invoke(
            [
                SystemMessage(content=rules),
                HumanMessage(content=json.dumps(payload, ensure_ascii=False)[:12000]),
            ]
        )
        text = msg.content if isinstance(msg.content, str) else str(msg.content)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"raw": text, "parse_error": True}
