#!/usr/bin/env python3
"""
Modal Memory Retrieval

Enhances memory_search results with modal logic-aware ranking:
- Boosts necessary items (boundaries, corrections) by 40%
- Decays old contingent items (framing changes) by 50% after 30 days
- Re-ranks results based on adjusted scores

Usage:
    python modal_retrieval.py --query "your query" --max-results 10
"""

import argparse
import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


# =============================================================================
# Configuration
# =============================================================================

DEFAULT_CONFIG = {
    "boost_necessary": 1.4,           # 40% boost to necessary items
    "decay_contingent": 0.5,          # 50% reduction after expiry
    "contingent_expiry_days": 30,     # Days before contingent items decay
    "necessary_boost_cap": 2.0,       # Max boost multiplier
    "decay_function": "linear",       # "linear" or "exponential"
    "min_score_threshold": 0.35,      # Filter low-confidence results
    "debug_mode": False,              # Show scoring breakdown
}


# =============================================================================
# Modality Detection
# =============================================================================

NECESSARY_MARKERS = [
    r'\[MODALITY:\s*necessary\]',
    r'\[KIND:\s*(boundary|correction|unresolved_tension)\]',
    r'\b(boundary|correction|invariant|always|never)\b',
]

CONTINGENT_MARKERS = [
    r'\[MODALITY:\s*contingent\]',
    r'\[KIND:\s*framing_change\]',
    r'\b(framing|task focus|hypothesis|session-specific)\b',
]


def detect_modality(snippet: str) -> str:
    """
    Detect modality from memory snippet.
    
    Returns: 'necessary', 'contingent', or 'unknown'
    """
    snippet_lower = snippet.lower()
    
    # Check for necessary markers
    for pattern in NECESSARY_MARKERS:
        if re.search(pattern, snippet, re.IGNORECASE):
            return 'necessary'
    
    # Check for contingent markers
    for pattern in CONTINGENT_MARKERS:
        if re.search(pattern, snippet, re.IGNORECASE):
            return 'contingent'
    
    return 'unknown'


# =============================================================================
# Age Calculation
# =============================================================================

def extract_file_date(path: str) -> datetime | None:
    """
    Extract date from memory file path.
    
    Handles:
    - memory/YYYY-MM-DD.md (dated daily notes)
    - memory/00-core-identity.md (evergreen files)
    - MEMORY.md (evergreen)
    
    Returns None for evergreen files (they don't decay).
    """
    path_obj = Path(path)
    filename = path_obj.name
    
    # Try to parse YYYY-MM-DD.md pattern
    match = re.match(r'(\d{4}-\d{2}-\d{2})\.md', filename)
    if match:
        try:
            return datetime.strptime(match.group(1), "%Y-%m-%d")
        except ValueError:
            return None
    
    # Evergreen files (no date = no decay)
    return None


def calculate_age_days(file_date: datetime | None) -> int | None:
    """
    Calculate age in days from file date.
    
    Returns None for evergreen files.
    """
    if file_date is None:
        return None
    
    now = datetime.now()
    delta = now - file_date
    return delta.days


# =============================================================================
# Scoring Functions
# =============================================================================

def calculate_decay_factor(
    age_days: int | None,
    expiry_days: int,
    decay_rate: float,
    decay_function: str = "linear"
) -> float:
    """
    Calculate decay factor for contingent items.
    
    Args:
        age_days: Age of item in days (None = evergreen)
        expiry_days: Days before decay starts
        decay_rate: Maximum decay factor (e.g., 0.5 = 50% reduction)
        decay_function: "linear" or "exponential"
    
    Returns:
        Decay factor (1.0 = no decay, 0.5 = 50% of original score)
    """
    if age_days is None:
        # Evergreen files don't decay
        return 1.0
    
    if age_days <= expiry_days:
        # Not yet expired
        return 1.0
    
    if decay_function == "exponential":
        # Exponential decay with half-life
        half_life = expiry_days
        decay_factor = 0.5 ** ((age_days - expiry_days) / half_life)
        # Ensure we don't go below the minimum decay rate
        return max(decay_factor, decay_rate)
    
    else:  # linear
        # Linear decay: after expiry, decay to minimum over expiry_days period
        days_past_expiry = age_days - expiry_days
        if days_past_expiry <= 0:
            return 1.0
        # Decay from 1.0 to decay_rate over expiry_days period
        progress = min(days_past_expiry / expiry_days, 1.0)
        return 1.0 - (progress * (1.0 - decay_rate))


def apply_modal_ranking(
    results: list[dict[str, Any]],
    config: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    """
    Apply modal ranking adjustments to memory_search results.
    
    Args:
        results: List of memory_search results
        config: Configuration dict (uses DEFAULT_CONFIG if None)
    
    Returns:
        Enhanced results with modality metadata and adjusted scores
    """
    if config is None:
        config = DEFAULT_CONFIG
    
    enhanced_results = []
    
    for result in results:
        snippet = result.get('snippet', '')
        path = result.get('path', '')
        original_score = result.get('score', 0.0) or 0.0  # Handle None/missing score
        
        # Detect modality
        modality = detect_modality(snippet)
        
        # Calculate age
        file_date = extract_file_date(path)
        age_days = calculate_age_days(file_date)
        
        # Calculate adjustment factor
        if modality == 'necessary':
            adjustment_factor = config['boost_necessary']
        elif modality == 'contingent':
            adjustment_factor = calculate_decay_factor(
                age_days=age_days,
                expiry_days=config['contingent_expiry_days'],
                decay_rate=config['decay_contingent'],
                decay_function=config['decay_function']
            )
        else:
            adjustment_factor = 1.0
        
        # Apply adjustment
        adjusted_score = original_score * adjustment_factor
        
        # Cap at maximum
        capped_score = min(adjusted_score, config['necessary_boost_cap'])
        
        # Build enhanced result
        enhanced_result = {
            'path': path,
            'snippet': snippet,
            'score': original_score,
            'startLine': result.get('startLine'),
            'endLine': result.get('endLine'),
            'modality': modality,
            'age_days': age_days,
            'adjustment_factor': adjustment_factor,
            'adjusted_score': adjusted_score,
            'capped_score': capped_score,
        }
        
        enhanced_results.append(enhanced_result)
    
    # Re-rank by capped score
    enhanced_results.sort(key=lambda x: x['capped_score'], reverse=True)
    
    # Add rank
    for i, result in enumerate(enhanced_results):
        result['rank'] = i + 1
    
    return enhanced_results


# =============================================================================
# Search Function
# =============================================================================

def search_with_modality(
    query: str,
    max_results: int = 6,
    min_score: float = 0.35,
    config: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    """
    Perform memory search with modal ranking.
    
    This is a wrapper around the OpenClaw memory_search tool.
    In production, this would call the actual tool via OpenClaw API.
    
    Args:
        query: Search query
        max_results: Maximum results to return
        min_score: Minimum score threshold
        config: Modal ranking configuration
    
    Returns:
        Enhanced results with modal ranking
    """
    # Placeholder: In production, call actual memory_search tool
    # For now, simulate with mock data
    print(f"[modal_retrieval] Would search for: {query}")
    print(f"[modal_retrieval] Max results: {max_results}, Min score: {min_score}")
    
    # Mock results for testing
    mock_results = [
        {
            'path': 'memory/2026-07-07.md',
            'startLine': 144,
            'endLine': 156,
            'score': 0.72,
            'snippet': '[MODALITY: necessary] [KIND: boundary] Don\'t send external messages without approval',
        },
        {
            'path': 'memory/2026-06-15.md',
            'startLine': 89,
            'endLine': 95,
            'score': 0.68,
            'snippet': '[MODALITY: contingent] [KIND: framing_change] Focus on eval framework this session',
        },
        {
            'path': 'memory/00-core-identity.md',
            'startLine': 12,
            'endLine': 18,
            'score': 0.65,
            'snippet': 'User prefers expert terminology and direct communication',
        },
    ]
    
    # Apply modal ranking
    ranked_results = apply_modal_ranking(mock_results, config)
    
    return ranked_results


# =============================================================================
# CLI Interface
# =============================================================================

def load_config_from_file(config_path: str) -> dict[str, Any]:
    """Load configuration from JSON file."""
    with open(config_path, 'r') as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser(
        description='Modal Memory Retrieval - Enhanced memory search with modal ranking'
    )
    
    parser.add_argument(
        '--query', '-q',
        type=str,
        required=True,
        help='Search query'
    )
    
    parser.add_argument(
        '--max-results', '-n',
        type=int,
        default=6,
        help='Maximum results to return (default: 6)'
    )
    
    parser.add_argument(
        '--min-score', '-s',
        type=float,
        default=0.35,
        help='Minimum score threshold (default: 0.35)'
    )
    
    parser.add_argument(
        '--config', '-c',
        type=str,
        help='Path to JSON configuration file'
    )
    
    parser.add_argument(
        '--output', '-o',
        type=str,
        help='Output file path (default: stdout)'
    )
    
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug mode with scoring breakdown'
    )
    
    args = parser.parse_args()
    
    # Load configuration
    config = DEFAULT_CONFIG.copy()
    if args.config:
        config.update(load_config_from_file(args.config))
    if args.debug:
        config['debug_mode'] = True
    
    # Perform search
    results = search_with_modality(
        query=args.query,
        max_results=args.max_results,
        min_score=args.min_score,
        config=config
    )
    
    # Filter by minimum score
    filtered_results = [
        r for r in results
        if r['capped_score'] >= config['min_score_threshold']
    ]
    
    # Output results
    output_data = {
        'query': args.query,
        'total_results': len(filtered_results),
        'config': config,
        'results': filtered_results,
    }
    
    output_json = json.dumps(output_data, indent=2, default=str)
    
    if args.output:
        with open(args.output, 'w') as f:
            f.write(output_json)
        print(f"✓ Results written to {args.output}")
    else:
        print(output_json)


if __name__ == '__main__':
    main()
