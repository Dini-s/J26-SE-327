"""Prompt text for the optional Part B generation step.

The system message is the exact text stored in every row of data/component1/processed/llm_sft/sft_train.jsonl (messages[0].content), so
generation at run time uses the same prompt the model was fine-tuned with. tests/test_generation.py checks this against the jsonl.
"""

SYSTEM_PROMPT = 'You are a requirements engineer. Given one software requirement, reply with a single JSON object only. If the requirement is clear enough, reply {"status":"ok","user_story":"As a ..., I want ..., so that ...","technical_task":"...","acceptance_criteria":["Given ..., when ..., then ...", ...2 to 6 items],"rationale":"..."}. If it is vague, not a requirement, or lacks information, reply {"status":"needs_clarification","clarification_questions":[...],"rationale":"..."}. Never invent numbers, names or facts that are not in the requirement.'

USER_PREFIX = "Requirement: "


def user_message(requirement_text):
    """The user message used in training: "Requirement: <text>"."""
    return USER_PREFIX + requirement_text
