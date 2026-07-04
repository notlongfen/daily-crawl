from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai

from gemini_uploader import get_or_create_store

SYSTEM_PROMPT = """You are OptiBot, the customer-support bot for OptiSigns.com.
• Tone: helpful, factual, concise.
• Only answer using the uploaded docs.
• Max 5 bullet points; else link to the doc.
• Cite up to 3 "Article URL:" lines per reply."""


def _content_text(content_block) -> str:
    if isinstance(content_block, dict):
        return content_block.get("text", "")
    return getattr(content_block, "text", "") or ""


def main() -> None:
    load_dotenv()
    question = " ".join(os.sys.argv[1:]).strip() or "How do I add a YouTube video?"
    data_dir = Path(os.getenv("DATA_DIR", "data"))

    client = genai.Client()
    store_name = get_or_create_store(client, data_dir)

    interaction = client.interactions.create(
        model=os.getenv("GEMINI_MODEL", "gemini-3.5-flash"),
        input=f"{SYSTEM_PROMPT}\n\nUser question: {question}",
        tools=[{
            "type": "file_search",
            "file_search_store_names": [store_name],
        }],
    )

    printed_any = False
    print(f"Question: {question}\n")

    for step in interaction.steps:
        if getattr(step, "type", None) != "model_output":
            continue
        for content in getattr(step, "content", []) or []:
            text = _content_text(content)
            if text:
                print(text)
                printed_any = True
            annotations = getattr(content, "annotations", None)
            if annotations:
                print("\nGemini file citations:")
                for annotation in annotations[:3]:
                    print(f"- {annotation}")

    if not printed_any:
        print(interaction)


if __name__ == "__main__":
    main()
