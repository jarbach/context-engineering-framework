#!/usr/bin/env python3
"""
Session Handoff Generator

Generates structured handoff artifacts from session transcripts.
Captures framing changes, boundaries, unresolved tensions, and corrections.

Usage:
    ./generate-handoff.py --session-id <id> --output <path>
    ./generate-handoff.py --transcript-file <path> --output <path>
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import TypedDict, Literal, Optional
import re

# Type definitions
HandoffKind = Literal["framing-change", "boundary", "unresolved-tension", "correction"]
ConfidenceLevel = Literal["low", "medium", "high"]
ConsentState = Literal["draft", "user-reviewed", "approved", "edited", "rejected"]
Modality = Literal["necessary", "contingent"]


class HandoffItem(TypedDict, total=False):
    kind: HandoffKind
    text: str
    sourceExcerpt: str
    reason: str
    confidence: ConfidenceLevel
    modality: Modality
    regressionTest: str
    turnNumber: int
    expiresAt: Optional[str]


class HandoffArtifact(TypedDict, total=False):
    id: str
    sessionId: str
    createdAt: str
    carryForward: list[HandoffItem]
    doNotCarryForward: list[HandoffItem]
    unresolvedTensions: list[HandoffItem]
    userCorrections: list[HandoffItem]
    consentState: ConsentState
    reviewedAt: Optional[str]
    expiresAt: Optional[str]
    confidence: ConfidenceLevel


# Detection patterns
PATTERNS = {
    "framing-change": [
        r"actually,\s*(let'?s|we should|we need to)",
        r"the real (issue|problem|goal) is",
        r"(forget|never mind)\s+.*\s+(let'?s|instead)",
        r"shift(ing)?\s+from\s+.*\s+to",
        r"scope\s+(change|shift|expand)",
        r"hold\s+(on|it)\s+right\s+there",
        r"let'?s\s+pause",
        r"new\s+(task|direction|priority)",
    ],
    "boundary": [
        r"(don'?t|do not|never)\s+(send|modify|change|execute)",
        r"(ask|confirm)\s+before",
        r"(require|need)\s+(explicit|approval|permission)",
        r"(constraint|boundary|limit|restriction)",
        r"(safety|security)\s+(rule|requirement|governance)",
        r"only\s+if\s+(I|you) (ask|request|approve)",
        r"(forbid|prohibit|block|prevent)",
    ],
    "unresolved-tension": [
        r"(pending|waiting|blocked|deferred)",
        r"(come back|return|revisit)\s+(to this|later)",
        r"(leave|keep)\s+(this|it)\s+(open|pending|unfinished)",
        r"(not yet|not done|incomplete|todo)",
        r"(next phase|next step|later|future)",
        r"(after.*arrives|when.*ready|once.*done)",
        r"(paused|on hold|waiting for)",
    ],
    "correction": [
        r"(actually|correction|fix|correct|wrong|mistake)",
        r"(typo|error|bug|issue|problem)\s+(in|with|on)",
        r"(should be|not|instead of|rather than)",
        r"(changed|updated|fixed)\s+(to|from)",
        r"(path|config|setting|value)\s+(typo|error|wrong)",
        r"(→|->|=>)\s+",  # Arrow notation for corrections
    ],
}


def load_transcript(session_id: Optional[str] = None, transcript_file: Optional[str] = None) -> list[dict]:
    """Load session transcript from OpenClaw API or file."""
    
    if transcript_file:
        with open(transcript_file, 'r') as f:
            data = json.load(f)
            
            # Handle different formats
            if isinstance(data, dict):
                # Wrapped format: {sessionId, turns}
                if 'turns' in data:
                    return data['turns']
                # Single turn or other dict format
                return [data]
            elif isinstance(data, list):
                # Direct list of turns
                return data
            else:
                raise ValueError(f"Unexpected transcript format: {type(data)}")
    
    if session_id:
        # Use OpenClaw sessions_history tool via subprocess
        import subprocess
        try:
            result = subprocess.run(
                ['openclaw', 'sessions', 'history', '--session', session_id, '--json'],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                # Normalize to list of turns
                if isinstance(data, dict) and 'turns' in data:
                    return data['turns']
                elif isinstance(data, list):
                    return data
        except Exception as e:
            print(f"Warning: Could not fetch session {session_id}: {e}", file=sys.stderr)
    
    raise ValueError("Either --session-id or --transcript-file must be provided")


def detect_pattern(text: str, pattern_type: HandoffKind) -> bool:
    """Check if text matches patterns for a given type."""
    text_lower = text.lower()
    for pattern in PATTERNS[pattern_type]:
        if re.search(pattern, text_lower, re.IGNORECASE):
            return True
    return False


def extract_source_excerpt(turn_text: str, max_length: int = 150) -> str:
    """Extract a concise excerpt from turn text."""
    # Remove whitespace and truncate
    excerpt = ' '.join(turn_text.split())
    if len(excerpt) > max_length:
        excerpt = excerpt[:max_length-3] + "..."
    return excerpt


def classify_turn(turn: dict, turn_number: int) -> Optional[HandoffItem]:
    """Classify a single turn into a handoff item if it matches."""
    # Only process user turns for handoff items
    role = turn.get('role', '')
    if role != 'user':
        return None
    
    text = turn.get('text', '') or turn.get('content', '')
    if not text:
        return None
    
    # Filter out non-substantive turns
    text_stripped = text.strip()
    
    # Skip pure URLs (common false positive for corrections)
    if re.match(r'^https?://\S+$', text_stripped):
        return None
    
    # Skip very short text (< 15 chars) - likely acks or noise
    if len(text_stripped) < 15:
        return None
    
    # Skip turns that are just whitespace or single words
    if len(text_stripped.split()) < 2:
        return None
    
    # Check each category
    for kind in ["framing-change", "boundary", "unresolved-tension", "correction"]:
        if detect_pattern(text, kind):  # type: ignore
            confidence = calculate_confidence(text, kind)  # type: ignore
            if confidence != "low":  # Filter out low-confidence items
                modality = determine_modality(kind)  # type: ignore
                expiry_days = 30 if modality == "contingent" else 365  # Contingent expires faster
                expires_at = (datetime.now() + timedelta(days=expiry_days)).isoformat()
                
                return HandoffItem(
                    kind=kind,  # type: ignore
                    text=generate_item_text(text, kind),  # type: ignore
                    sourceExcerpt=extract_source_excerpt(text),
                    reason=generate_reason(kind, text),
                    confidence=confidence,
                    modality=modality,
                    expiresAt=expires_at,
                    turnNumber=turn_number
                )
    
    return None


def calculate_confidence(text: str, kind: HandoffKind) -> ConfidenceLevel:
    """Calculate confidence level based on pattern matches and context."""
    match_count = sum(1 for pattern in PATTERNS[kind] if re.search(pattern, text.lower()))
    
    if match_count >= 2:
        return "high"
    elif match_count == 1:
        # Boost confidence for explicit keywords
        explicit_keywords = {
            "framing-change": ["actually", "instead", "shift"],
            "boundary": ["don't", "never", "ask before"],
            "unresolved-tension": ["pending", "waiting", "blocked"],
            "correction": ["actually", "correction", "typo", "should be"],
        }
        if any(kw in text.lower() for kw in explicit_keywords.get(kind, [])):
            return "high"
        return "medium"
    else:
        return "low"


def generate_item_text(raw_text: str, kind: HandoffKind) -> str:
    """Generate concise item text from raw turn text."""
    # Remove common filler phrases
    filler_patterns = [
        r"^actually,\s*",
        r"^let'?s\s+",
        r"^I\s+(need|want|would like)\s+",
        r"^don'?t\s+",
    ]
    
    cleaned = raw_text
    for pattern in filler_patterns:
        cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
    
    # For framing changes, preserve the full shift context
    if kind == 'framing-change':
        # Keep "hold it right there" + reason if present
        if 'hold' in cleaned.lower() and 'there' in cleaned.lower():
            return "Pause current task: " + cleaned.strip()[:60]
        elif 'shift' in cleaned.lower() or 'actually' in raw_text.lower():
            return cleaned.strip()[:80]
    
    # Extract key clause for other types
    sentences = re.split(r'[.!?]', cleaned)
    if sentences:
        candidate = sentences[0].strip()
        if 15 < len(candidate) <= 80:
            return candidate
        elif len(candidate) > 80:
            return candidate[:77] + "..."
    
    # Fallback: truncate raw text
    return raw_text[:80].strip() + ("..." if len(raw_text) > 80 else "")


def determine_modality(kind: HandoffKind) -> Modality:
    """
    Determine if an item is necessary (invariant) or contingent (session-specific).
    
    Based on modal logic interpretation of neural networks:
    - Necessary: Properties that must persist across "possible worlds" (sessions)
    - Contingent: Properties that may vary between sessions
    
    See: https://hackernoon.com/modal-logic-and-neural-networks
    """
    modality_map = {
        "boundary": "necessary",           # Constraints are invariant
        "correction": "necessary",          # Fixed errors remain true
        "unresolved-tension": "necessary",  # Pending work persists until resolved
        "framing-change": "contingent",     # Task focus may shift again
    }
    return modality_map.get(kind, "contingent")


def generate_reason(kind: HandoffKind, text: str) -> str:
    """Generate reason string based on kind and content."""
    reasons = {
        "framing-change": "Task scope or direction shifted",
        "boundary": "User-set constraint or approval requirement",
        "unresolved-tension": "Work intentionally left pending",
        "correction": "User-provided fix to prior error",
    }
    return reasons.get(kind, "Relevant session content")


def deduplicate_items(items: list[HandoffItem]) -> list[HandoffItem]:
    """Remove duplicate items based on text similarity."""
    seen_texts = set()
    unique = []
    
    for item in items:
        text_key = item['text'][:50].lower()
        if text_key not in seen_texts:
            seen_texts.add(text_key)
            unique.append(item)
    
    return unique


def categorize_items(items: list[HandoffItem]) -> dict:
    """Categorize items into carryForward, unresolvedTensions, userCorrections."""
    carry_forward = []
    unresolved = []
    corrections = []
    
    for item in items:
        if item['kind'] == 'unresolved-tension':
            unresolved.append(item)
        elif item['kind'] == 'correction':
            corrections.append(item)
        else:
            carry_forward.append(item)
    
    # Separate by modality for better organization
    necessary_items = [item for item in carry_forward if item.get('modality') == 'necessary']
    contingent_items = [item for item in carry_forward if item.get('modality') == 'contingent']
    
    return {
        'carryForward': necessary_items + contingent_items,  # Keep ordering but grouped
        'carryForwardNecessary': necessary_items,
        'carryForwardContingent': contingent_items,
        'unresolvedTensions': unresolved,
        'userCorrections': corrections,
    }


def generate_handoff(transcript: list[dict], session_id: str) -> HandoffArtifact:
    """Generate complete handoff artifact from transcript."""
    items = []
    
    for i, turn in enumerate(transcript, 1):
        item = classify_turn(turn, i)
        if item:
            items.append(item)
    
    # Deduplicate
    unique_items = deduplicate_items(items)
    
    # Categorize
    categorized = categorize_items(unique_items)
    
    # Determine overall confidence
    if not unique_items:
        overall_confidence = "low"
    elif any(item['confidence'] == 'high' for item in unique_items):
        overall_confidence = "high"
    elif any(item['confidence'] == 'medium' for item in unique_items):
        overall_confidence = "medium"
    else:
        overall_confidence = "low"
    
    # Set expiration based on modality (already set per-item, but overall artifact has default)
    # Use longest expiry from items, or default 90 days
    default_expiry = (datetime.now() + timedelta(days=90)).isoformat()
    if unique_items:
        max_expiry = max(datetime.fromisoformat(item.get('expiresAt', default_expiry)) for item in unique_items)
        expires_at = max_expiry.isoformat()
    else:
        expires_at = default_expiry
    
    return HandoffArtifact(
        id=f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{session_id[-8:]}",
        sessionId=session_id,
        createdAt=datetime.now().isoformat(),
        carryForward=categorized['carryForward'],
        unresolvedTensions=categorized['unresolvedTensions'],
        userCorrections=categorized['userCorrections'],
        doNotCarryForward=[],  # Empty by default, populated during review
        consentState="draft",
        expiresAt=expires_at,
        confidence=overall_confidence
    )


def format_markdown(handoff: HandoffArtifact) -> str:
    """Format handoff artifact as markdown for review."""
    # Count by modality
    necessary_count = sum(1 for item in handoff.get('carryForward', []) if item.get('modality') == 'necessary')
    contingent_count = sum(1 for item in handoff.get('carryForward', []) if item.get('modality') == 'contingent')
    
    md = f"""# Session Handoff Artifact

**ID:** {handoff.get('id', 'N/A')}  
**Session:** {handoff.get('sessionId', 'N/A')}  
**Created:** {handoff.get('createdAt', 'N/A')}  
**Expires:** {handoff.get('expiresAt', 'N/A')}  
**Consent State:** {handoff.get('consentState', 'draft')}  
**Overall Confidence:** {handoff.get('confidence', 'unknown')}  
**Modal Distribution:** {necessary_count} necessary, {contingent_count} contingent

---

## Carry Forward ({len(handoff.get('carryForward', []))} items)

"""
    
    # Group by modality
    carry_forward = handoff.get('carryForward', [])
    necessary_items = [i for i in carry_forward if i.get('modality') == 'necessary']
    contingent_items = [i for i in carry_forward if i.get('modality') == 'contingent']
    
    if necessary_items:
        md += f"### Necessary ({len(necessary_items)} items) — Invariant across sessions\n\n"
        for i, item in enumerate(necessary_items, 1):
            md += format_handoff_item(i, item)
    
    if contingent_items:
        md += f"\n### Contingent ({len(contingent_items)} items) — Session-specific, expires in 30 days\n\n"
        for i, item in enumerate(contingent_items, 1):
            md += format_handoff_item(i, item)
    
    md += f"""
## Unresolved Tensions ({len(handoff.get('unresolvedTensions', []))} items)

"""
    
    for i, item in enumerate(handoff.get('unresolvedTensions', []), 1):
        md += format_handoff_item(i, item, prefix="UT")
    
    md += f"""
## User Corrections ({len(handoff.get('userCorrections', []))} items)

"""
    
    for i, item in enumerate(handoff.get('userCorrections', []), 1):
        md += format_handoff_item(i, item, prefix="UC")
    
    md += """
---

## Review Actions

Run `./review-handoff.sh <this-file>` to review and approve/reject items.

</details>
"""
    
    return md


def format_handoff_item(number: int, item: HandoffItem, prefix: str = "") -> str:
    """Format a single handoff item as markdown."""
    kind = item.get('kind', 'unknown')
    text = item.get('text', 'N/A')
    confidence = item.get('confidence', 'unknown')
    modality = item.get('modality', 'unknown')
    source = f"Turn {item.get('turnNumber', 'N/A')}"
    reason = item.get('reason', 'N/A')
    expires = item.get('expiresAt', 'N/A')[:10] if item.get('expiresAt') else 'N/A'
    
    md = f"""### {number}. [{kind}] {text}

- **Confidence:** {confidence}
- **Modality:** {modality}
- **Expires:** {expires}
- **Source:** {source}
- **Reason:** {reason}
"""
    if item.get('regressionTest'):
        md += f"- **Regression Test:** `{item['regressionTest']}`\n"
    md += "\n"
    
    return md


def main():
    parser = argparse.ArgumentParser(description="Generate session handoff artifact")
    parser.add_argument("--session-id", help="OpenClaw session ID")
    parser.add_argument("--transcript-file", help="Path to transcript JSON file")
    parser.add_argument("--output", required=True, help="Output path for handoff markdown")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of markdown")
    
    args = parser.parse_args()
    
    if not args.session_id and not args.transcript_file:
        print("Error: Either --session-id or --transcript-file must be provided", file=sys.stderr)
        sys.exit(1)
    
    # Load transcript
    try:
        transcript = load_transcript(args.session_id, args.transcript_file)
    except Exception as e:
        print(f"Error loading transcript: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Generate handoff
    session_id = args.session_id or Path(args.transcript_file).stem
    handoff = generate_handoff(transcript, session_id)
    
    # Format output
    if args.json:
        output = json.dumps(handoff, indent=2)
    else:
        output = format_markdown(handoff)
    
    # Write output
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w') as f:
        f.write(output)
    
    print(f"✓ Handoff artifact written to: {output_path}")
    print(f"  Items: {len(handoff.get('carryForward', []))} carry-forward, "
          f"{len(handoff.get('unresolvedTensions', []))} unresolved, "
          f"{len(handoff.get('userCorrections', []))} corrections")
    print(f"  Confidence: {handoff.get('confidence', 'unknown')}")
    print(f"\nNext: Run ./review-handoff.sh {output_path} to review and approve")


if __name__ == "__main__":
    main()
