"""Claude API wrapper for content analysis."""

import asyncio
import json

import anthropic

from src.config import ANTHROPIC_API_KEY, ANALYSIS_MODEL
from src.analysis.prompts import ANALYSIS_SYSTEM_PROMPT, build_analysis_prompt


def get_client() -> anthropic.Anthropic:
    """Get an Anthropic client."""
    key = ANTHROPIC_API_KEY or None  # Let SDK use env var if config is empty
    return anthropic.Anthropic(api_key=key)


async def analyze_content(
    candidate_name: str,
    party: str,
    office: str,
    state: str,
    source_url: str,
    raw_text: str,
    model: str = ANALYSIS_MODEL,
) -> dict:
    """Analyze a piece of content for AI-relevant positions.

    Returns parsed JSON response from Claude.
    """
    client = get_client()
    prompt = build_analysis_prompt(
        candidate_name=candidate_name,
        party=party,
        office=office,
        state=state,
        source_url=source_url,
        raw_text=raw_text,
    )

    # Run synchronous API call in executor to avoid blocking
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None,
        lambda: client.messages.create(
            model=model,
            max_tokens=4096,
            system=ANALYSIS_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        ),
    )

    # Extract text from response
    text = response.content[0].text

    # Parse JSON from response (handle markdown code blocks)
    text = text.strip()
    if text.startswith("```"):
        # Remove markdown code block
        lines = text.split("\n")
        text = "\n".join(lines[1:-1]) if len(lines) > 2 else text
    if text.startswith("```json"):
        text = text[7:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        # Try to extract JSON from the response
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            result = json.loads(text[start:end])
        else:
            result = {"is_ai_relevant": False, "excerpts": [], "_parse_error": True}

    return result


async def analyze_content_batch(
    items: list[dict],
    model: str = ANALYSIS_MODEL,
    max_concurrent: int = 3,
    delay: float = 1.0,
) -> list[dict]:
    """Analyze multiple content items with concurrency limiting.

    Args:
        items: List of dicts with keys matching analyze_content params
        model: Claude model to use
        max_concurrent: Max concurrent API calls
        delay: Delay between calls in seconds

    Returns:
        List of (content_id, result) tuples
    """
    semaphore = asyncio.Semaphore(max_concurrent)
    results = []

    async def _analyze_one(item: dict):
        async with semaphore:
            try:
                result = await analyze_content(
                    candidate_name=item["candidate_name"],
                    party=item["party"],
                    office=item["office"],
                    state=item["state"],
                    source_url=item["source_url"],
                    raw_text=item["raw_text"],
                    model=model,
                )
                results.append((item["content_id"], result))
            except Exception as e:
                results.append((item["content_id"], {
                    "is_ai_relevant": False,
                    "excerpts": [],
                    "_error": str(e),
                }))
            await asyncio.sleep(delay)

    tasks = [_analyze_one(item) for item in items]
    await asyncio.gather(*tasks)

    return results
