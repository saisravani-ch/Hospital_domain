from __future__ import annotations

import re

DISCOVERY = "discovery"
BOOKING = "booking"
QA = "qa"

# Keywords that signal a booking intent (fast-path, no LLM needed)
_BOOKING_PATTERNS = re.compile(
    r"\b(book|appointment|schedule|reschedule|cancel|slot|"
    r"available|free\s+slot|"     # availability check within booking context
    r"i want to (see|meet|consult|visit)|"
    r"can i (see|meet|consult|visit))\b",
    re.IGNORECASE,
)

# Keywords that signal a discovery (search) intent
_DISCOVERY_PATTERNS = re.compile(
    r"\b(find|search|look|need|recommend|suggest|"
    r"doctor for|specialist|show\s+me|list|"
    r"cardiolog|ortho|neurolog|dermatolog|pediatr|gynec|"
    r"ent|ophthal|dentist|diabet|physio|"
    r"who\s+(is|treats|can|speaks))\b",
    re.IGNORECASE,
)


def classify(message: str) -> str:
    """Classify a user message into a domain. Cheap keyword matching."""
    if _BOOKING_PATTERNS.search(message):
        return BOOKING
    if _DISCOVERY_PATTERNS.search(message):
        return DISCOVERY
    return QA
