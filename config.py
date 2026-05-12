"""Configuration for Dewey agent."""

import os
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).parent
DB_DIR = BASE_DIR / "db"
DB_PATH = DB_DIR / "memory.db"
PLANS_DIR = BASE_DIR / "plans"

# Ensure directories exist
DB_DIR.mkdir(exist_ok=True)
PLANS_DIR.mkdir(exist_ok=True)

# API keys from environment
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# Model settings
CLAUDE_MODEL = "claude-sonnet-4-20250514"

# Memory settings
MAX_MEMORY_RESULTS = 5
PROFILE_COLLECTION = "teacher_profile"
CONVERSATION_COLLECTION = "conversations"

# FERPA patterns — compiled at import time for speed
import re

# Framework terms that look like Firstname Lastname but aren't
_FRAMEWORK_TERMS = {"WIDA", "SIOP", "QTEL", "CELDT", "ACCESS", "ELPAC"}

FERPA_PATTERNS = [
    # Name (two capitalized words, not framework terms) followed by score/grade/level words
    re.compile(
        r"\b(?!(?:" + "|".join(_FRAMEWORK_TERMS) + r")\b)"
        r"[A-Z][a-z]+\s+[A-Z][a-z]+\s*(?:'s\s+)?"
        r"(?:grade|scored?|levels?|GPA|IEP|504|assessment|evaluation)\b",
    ),
    # Name with common support-plan phrasing
    re.compile(
        r"\b(?!(?:" + "|".join(_FRAMEWORK_TERMS) + r")\b)"
        r"[A-Z][a-z]+\s+[A-Z][a-z]+\s+"
        r"(?:has|needs|receives|is\s+on|is\s+under)\s+(?:an?\s+)?"
        r"(?:IEP|504|504\s+plan|accommodation|intervention|evaluation)\b",
    ),
    # Student ID patterns
    re.compile(r"\b(?:student\s*(?:id|#|number))\s*[:.]?\s*\d{4,}\b", re.IGNORECASE),
    # IEP/504 with names
    re.compile(
        r"\b(?:IEP|504\s*plan)\s+(?:for|of)\s+[A-Z][a-z]+\s+[A-Z][a-z]+\b",
    ),
    # SSN patterns
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    # Email addresses that look like student emails
    re.compile(
        r"\b(?:student\s*(?:email|e-mail)|email)\s*[:.]?\s*"
        r"[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b[a-z]+\.\d+@\S+\.edu\b", re.IGNORECASE),
]

FERPA_REMINDER = (
    "\n\n---\n"
    "*I noticed what looked like student-identifiable information and "
    "removed it before processing. You can reference students by proficiency "
    "level, grade band, or language group -- I'll be just as helpful without "
    "names attached.*"
)
