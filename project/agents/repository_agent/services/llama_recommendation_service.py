import json
import os

import httpx

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
LLAMA_MODEL = os.getenv("LLAMA_MODEL", "llama3.2:3b")


async def generate_recommendations(evidence: dict) -> dict:
    """
    Generate candidate recommendations from supplied HRIM/SHAP/USKG evidence.
    Evidence must be retrieved by your backend, not trusted from the browser.
    """

    prompt = f"""
You are a software architecture recommendation assistant.

Use only the evidence provided below.

Evidence:
{json.dumps(evidence, ensure_ascii=False, default=str)}

Return JSON with this structure:
{{
  "summary": "Short evidence-based explanation",
  "recommendations": [
    {{
      "title": "Short title",
      "description": "Specific recommended action",
      "evidence": ["Exact feature or metric from the evidence"],
      "priority": "high, medium, or low",
      "validation_required": true
    }}
  ]
}}

Rules:
- Never invent metrics, SHAP values, files, or dependencies.
- A positive SHAP value means the feature pushes the model output
  toward class 1; it does not prove an architectural defect.
- Do not claim proxy predictions are confirmed architecture drift.
- Recommend source-code inspection before proposing a refactor.
- If evidence is insufficient, say so and return no recommendations.
"""

    async with httpx.AsyncClient(timeout=180.0) as client:
        response = await client.post(
            f"{OLLAMA_URL.rstrip('/')}/api/chat",
            json={
                "model": LLAMA_MODEL,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Provide cautious, evidence-grounded software "
                            "engineering recommendations."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                "format": "json",
                "stream": False,
                "options": {"temperature": 0},
            },
        )

        response.raise_for_status()
        result = response.json()

    content = result.get("message", {}).get("content", "")
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError("Llama returned invalid JSON.") from exc

    if not isinstance(parsed, dict):
        raise ValueError("Llama response must be a JSON object.")

    if not isinstance(parsed.get("recommendations"), list):
        raise ValueError("Llama response has no recommendations array.")

    return parsed
