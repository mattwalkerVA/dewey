"""First-run onboarding conversation to build a teacher profile."""

import json
from collections.abc import Callable

import anthropic

import config
from memory import Memory
from prompts import MEMORY_EXTRACTION_PROMPT, ONBOARDING_PROMPT


def _strip_code_fences(text: str) -> str:
    """Extract JSON payloads that may be wrapped in markdown fences."""
    if text.startswith("```"):
        return text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return text


def extract_profile_facts(
    client: anthropic.Anthropic,
    teacher_msg: str,
    assistant_msg: str,
) -> list[dict]:
    """Use Claude to extract profile facts from an onboarding exchange."""
    try:
        response = client.messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": MEMORY_EXTRACTION_PROMPT.format(
                        teacher_message=teacher_msg,
                        assistant_response=assistant_msg,
                    ),
                }
            ],
        )
        text = _strip_code_fences(response.content[0].text.strip())
        return json.loads(text)
    except Exception:
        return []


def store_profile_facts(
    memory: Memory,
    facts: list[dict],
    sanitize_text: Callable[[str], tuple[str, bool]],
) -> None:
    """Store sanitized onboarding facts, collapsing invalid or duplicate entries."""
    for fact in facts:
        content = str(fact.get("content", "")).strip()
        if not content:
            continue
        cleaned_content, _ = sanitize_text(content)
        if not cleaned_content.strip():
            continue
        memory.store(
            content=cleaned_content,
            collection=config.PROFILE_COLLECTION,
            category=fact.get("category", "profile"),
        )


def run_onboarding(
    memory: Memory,
    sanitize_text: Callable[[str], tuple[str, bool]],
) -> None:
    """Run the onboarding conversation to build a teacher profile."""
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    messages: list[dict] = []

    # Get initial greeting
    try:
        response = client.messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=1024,
            system=ONBOARDING_PROMPT,
            messages=[{"role": "user", "content": "Hi, I'm a new teacher using this tool."}],
        )
        greeting = response.content[0].text
    except Exception as exc:
        print(f"\nUnable to start onboarding right now: {exc}\n")
        return

    print(f"\n🎓 Dewey: {greeting}\n")
    messages.append({"role": "user", "content": "Hi, I'm a new teacher using this tool."})
    messages.append({"role": "assistant", "content": greeting})

    print("(Type 'done' when you're ready to start planning)\n")

    while True:
        try:
            teacher_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not teacher_input:
            continue

        if teacher_input.lower() == "done":
            print("\n🎓 Dewey: Great — I've got a good picture of your "
                  "teaching context. Let's plan.\n")
            break

        cleaned_input, had_pii = sanitize_text(teacher_input)
        messages.append({"role": "user", "content": cleaned_input})

        try:
            response = client.messages.create(
                model=config.CLAUDE_MODEL,
                max_tokens=1024,
                system=ONBOARDING_PROMPT,
                messages=messages,
            )
        except Exception as exc:
            print(f"\n🎓 Dewey: I hit an error during onboarding: {exc}\n")
            messages.pop()
            continue

        assistant_msg = response.content[0].text
        messages.append({"role": "assistant", "content": assistant_msg})

        output = assistant_msg
        if had_pii:
            output += config.FERPA_REMINDER
        print(f"\n🎓 Dewey: {output}\n")

        # Extract and store profile facts from this exchange
        facts = extract_profile_facts(client, cleaned_input, assistant_msg)
        store_profile_facts(memory, facts, sanitize_text)

    # Store the full onboarding conversation too
    full_convo = "\n".join(
        f"{'Teacher' if m['role'] == 'user' else 'Dewey'}: {m['content']}"
        for m in messages
    )
    cleaned_convo, _ = sanitize_text(full_convo)
    try:
        memory.store(
            content=cleaned_convo,
            collection=config.CONVERSATION_COLLECTION,
            category="onboarding",
            metadata={"type": "onboarding"},
        )
    except Exception as exc:
        print(f"\nUnable to save onboarding context: {exc}\n")
