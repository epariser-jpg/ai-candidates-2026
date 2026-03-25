"""Parse and validate Claude analysis responses."""

from src.config import AI_TAGS


VALID_SENTIMENTS = {"supportive", "cautious", "opposed", "neutral", "mixed"}


def validate_and_clean(result: dict) -> dict:
    """Validate and clean a Claude analysis response.

    Ensures all fields are present and within expected ranges.
    Returns a cleaned result dict.
    """
    cleaned = {
        "is_ai_relevant": bool(result.get("is_ai_relevant", False)),
        "excerpts": [],
    }

    for excerpt in result.get("excerpts", []):
        clean_excerpt = {
            "excerpt_text": str(excerpt.get("excerpt_text", ""))[:2000],
            "context_text": str(excerpt.get("context_text", ""))[:1000],
            "position_summary": str(excerpt.get("position_summary", ""))[:500],
            "sentiment": excerpt.get("sentiment", "neutral"),
            "confidence": float(excerpt.get("confidence", 0.5)),
            "tags": [],
        }

        # Validate sentiment
        if clean_excerpt["sentiment"] not in VALID_SENTIMENTS:
            clean_excerpt["sentiment"] = "neutral"

        # Clamp confidence
        clean_excerpt["confidence"] = max(0.0, min(1.0, clean_excerpt["confidence"]))

        # Process tags
        raw_tags = excerpt.get("tags", [])
        for tag in raw_tags:
            tag = str(tag).strip().lower()
            if tag.startswith("new:"):
                # New tag suggestion — clean and add
                new_tag = tag[4:].strip().replace(" ", "_")
                if new_tag:
                    clean_excerpt["tags"].append(new_tag)
            elif tag in AI_TAGS:
                clean_excerpt["tags"].append(tag)
            else:
                # Try to fuzzy match known tags
                for known in AI_TAGS:
                    if tag.replace(" ", "_") == known or tag.replace("-", "_") == known:
                        clean_excerpt["tags"].append(known)
                        break

        # Skip empty excerpts
        if clean_excerpt["excerpt_text"]:
            cleaned["excerpts"].append(clean_excerpt)

    # If we have excerpts, it's AI relevant
    if cleaned["excerpts"]:
        cleaned["is_ai_relevant"] = True

    return cleaned
