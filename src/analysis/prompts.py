"""Prompt templates for Claude AI content analysis."""

from src.config import AI_TAGS


ANALYSIS_SYSTEM_PROMPT = """You are an expert political analyst specializing in technology policy. \
You are analyzing political candidates' public statements and website content to identify positions \
related to artificial intelligence and AI-adjacent topics.

You must identify BOTH:
1. Explicit AI mentions (artificial intelligence, machine learning, AI, ChatGPT, etc.)
2. AI-adjacent topics that are deeply interwoven with AI even if AI isn't named:
   - Automation and job displacement
   - Algorithmic bias and fairness
   - Surveillance technology and facial recognition
   - Deepfakes and AI-generated misinformation
   - Tech regulation (especially of AI companies)
   - Data privacy related to automated systems
   - Autonomous weapons and military technology
   - Semiconductor/chip policy and manufacturing
   - Competition with China on advanced technology
   - AI in education, healthcare, agriculture
   - Copyright and intellectual property in the age of generative AI
   - Government use of automated decision-making

Be thorough but precise. Only flag content that genuinely relates to these topics. \
A generic mention of "technology" without connection to AI/automation does not qualify."""


def build_analysis_prompt(
    candidate_name: str,
    party: str,
    office: str,
    state: str,
    source_url: str,
    raw_text: str,
    tag_list: list[str] | None = None,
) -> str:
    """Build the analysis prompt for a piece of content."""
    tags = tag_list or AI_TAGS
    tags_str = ", ".join(tags)

    return f"""Analyze the following content from a political candidate's website.

**Candidate:** {candidate_name} ({party}), running for {office} in {state}
**Source:** {source_url}

---
{raw_text[:8000]}
---

Identify ALL passages where the CANDIDATE THEMSELVES discusses or takes a position on AI or AI-adjacent topics (see your system instructions for the full list).

IMPORTANT: Do NOT flag:
- Standard website privacy policies, cookie notices, or terms of service
- Third-party tracking/analytics tools used by the campaign website
- Generic mentions of "technology" without connection to AI/automation policy
- Boilerplate legal text about data collection
These are website infrastructure, NOT the candidate's policy positions.

Return a JSON object with this exact structure:
{{
  "is_ai_relevant": true or false,
  "excerpts": [
    {{
      "excerpt_text": "exact quote from the text (keep under 500 chars)",
      "context_text": "the surrounding paragraph for context (keep under 300 chars)",
      "position_summary": "1-2 sentence summary of what the candidate's stance is",
      "tags": ["tag1", "tag2"],
      "sentiment": "supportive|cautious|opposed|neutral|mixed",
      "confidence": 0.85
    }}
  ]
}}

Rules:
- If no AI-relevant content exists, return: {{"is_ai_relevant": false, "excerpts": []}}
- Use tags from this predefined list: {tags_str}
- You may suggest new tags by prefixing with "NEW:" (e.g., "NEW:ai_antitrust")
- "sentiment" describes the candidate's attitude toward the AI-related topic:
  - "supportive" = embraces or promotes the use/development of AI
  - "cautious" = acknowledges benefits but emphasizes need for guardrails
  - "opposed" = wants to restrict, ban, or heavily regulate
  - "neutral" = mentions without clear position
  - "mixed" = takes both positive and negative stances
- "confidence" is your assessment (0.0-1.0) of how clearly this is about AI/adjacent topics
- Return ONLY valid JSON, no other text"""
