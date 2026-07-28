import asyncio
import json
import logging

from openai import AsyncOpenAI

from app.models import CodeChunk, ReviewComment
from app.analysis.prompts import SYSTEM_PROMPT, build_review_prompt

logger = logging.getLogger(__name__)


class LLMReviewer:
    def __init__(self, api_key: str, model: str):
        self.model = model
        self._api_key = api_key
        self.client: AsyncOpenAI | None = None

    async def start(self):
        self.client = AsyncOpenAI(
            api_key=self._api_key,
            base_url="https://openrouter.ai/api/v1",
        )

    async def close(self):
        if self.client:
            await self.client.close()

    async def review_chunk(self, chunk: CodeChunk, profile: str = "all") -> list[ReviewComment]:
        prompt = build_review_prompt(chunk, profile)

        for attempt in range(3):
            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    max_tokens=2048,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                )

                text = response.choices[0].message.content.strip()
                text = _strip_markdown_fences(text)
                issues = json.loads(text)

                return [
                    ReviewComment(
                        file=chunk.file_path,
                        line=issue["line"],
                        severity=issue["severity"],
                        issue=issue["issue"],
                        suggestion=issue["suggestion"],
                    )
                    for issue in issues
                ]

            except Exception as e:
                if attempt < 2:
                    await asyncio.sleep(2 ** attempt)
                    continue
                logger.warning("LLM review failed for %s: %s", chunk.file_path, e)
                return []

    async def review_chunks(
        self, chunks: list[CodeChunk], profile: str = "all", max_concurrent: int = 5,
    ) -> list[ReviewComment]:
        sem = asyncio.Semaphore(max_concurrent)

        async def _limited(chunk: CodeChunk) -> list[ReviewComment]:
            async with sem:
                return await self.review_chunk(chunk, profile)

        results = await asyncio.gather(*[_limited(c) for c in chunks])
        return [issue for batch in results for issue in batch]


def _strip_markdown_fences(text: str) -> str:
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
    if text.endswith("```"):
        text = text.rsplit("\n", 1)[0]
    return text.strip()
