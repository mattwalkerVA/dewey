"""Tool: Differentiate a lesson plan by WIDA proficiency level.

Takes a lesson plan and a target proficiency level, then uses Claude to
produce a scaffolded version with concrete language supports. This runs
as a sub-call to the API - the main agent delegates differentiation here.
"""

import anthropic

import config

DIFFERENTIATION_PROMPT = """\
You are an expert in sheltered instruction and differentiation for English \
learners. Given a lesson plan and a target WIDA proficiency level, produce a \
scaffolded version of the lesson.

## Your approach by WIDA level

**Level 1 (Entering)**:
- Heavy visual/graphic support for all activities
- Sentence frames and word banks for every output task
- L1 support where possible (bilingual glossaries, cognate lists)
- Reduce linguistic complexity while maintaining content rigor
- Focus on receptive skills (listening, reading with support) before productive

**Level 2 (Emerging)**:
- Visual support with some reduction from Level 1
- Sentence starters and paragraph frames
- Pre-taught vocabulary with visual/contextual definitions
- Partner work with structured interaction protocols
- Modified text with key vocabulary highlighted

**Level 3 (Developing)**:
- Graphic organizers for academic language production
- Word banks for content-specific vocabulary (not basic words)
- Structured discussion protocols (think-pair-share, numbered heads)
- Anchor charts for language functions
- Some text modification, primarily glossing difficult passages

**Level 4 (Expanding)**:
- Minimal scaffolding — focus on academic register and precision
- Discussion protocols that push extended discourse
- Writing support through mentor texts and rubrics
- Vocabulary work focused on nuance and connotation
- Peer review and collaborative editing

**Level 5 (Bridging)**:
- Near grade-level expectations with targeted support for:
  - Idiomatic language and cultural references
  - Advanced academic vocabulary (Tier 3)
  - Complex syntax in writing
  - Register-shifting between contexts

## Output format

Return a scaffolded lesson plan with:
1. **Modified Language Objective** — appropriate for this proficiency level
2. **Key Vocabulary** — with student-friendly definitions and visual cues
3. **Scaffolded Procedure** — step by step, noting where supports are added
4. **Materials Needed** — any additional scaffolds (graphic organizers, word banks, sentence frames)
5. **Assessment Modifications** — how to assess the same content at this language level

Be specific and practical. A teacher should be able to pick this up and use it tomorrow.

## Lesson plan to differentiate:
{lesson_plan}

## Target WIDA proficiency level: {wida_level}

## Additional context:
{context}
"""


def differentiate_lesson(
    lesson_plan: str,
    wida_level: int,
    context: str = "",
) -> str:
    """Take a lesson plan and return a version scaffolded for the given WIDA level."""
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    response = client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=4096,
        messages=[
            {
                "role": "user",
                "content": DIFFERENTIATION_PROMPT.format(
                    lesson_plan=lesson_plan,
                    wida_level=wida_level,
                    context=context or "No additional context provided.",
                ),
            }
        ],
    )
    return response.content[0].text


# Tool definitions for Claude API tool_use
TOOLS = [
    {
        "name": "differentiate_lesson",
        "description": (
            "Take a lesson plan and produce a scaffolded version for a specific "
            "WIDA proficiency level (1-5). Returns a complete differentiated plan "
            "with modified language objectives, vocabulary support, scaffolded "
            "procedures, and assessment modifications. Use this when a teacher "
            "wants to adapt a lesson for a specific proficiency group."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "lesson_plan": {
                    "type": "string",
                    "description": "The full lesson plan text to differentiate.",
                },
                "wida_level": {
                    "type": "integer",
                    "description": "Target WIDA proficiency level (1-5).",
                    "minimum": 1,
                    "maximum": 5,
                },
                "context": {
                    "type": "string",
                    "description": (
                        "Additional context about the students or classroom "
                        "(e.g. 'mostly Spanish L1 speakers', 'co-taught class'). Optional."
                    ),
                },
            },
            "required": ["lesson_plan", "wida_level"],
        },
    },
]


def handle_tool_call(name: str, input_data: dict) -> str:
    """Execute a differentiation tool call and return the result as a string."""
    if name == "differentiate_lesson":
        return differentiate_lesson(
            lesson_plan=input_data["lesson_plan"],
            wida_level=input_data["wida_level"],
            context=input_data.get("context", ""),
        )
    return f"Unknown differentiation tool: {name}"
