#!/usr/bin/env python3
"""
OpenClaw Agent Evaluation Results Analyzer

Usage:
  ./analyze-results.py                    # Latest results summary
  ./analyze-results.py --trend 7d         # 7-day trend analysis
  ./analyze-results.py --min-reliability 0.85  # Check threshold
  ./analyze-results.py --output markdown  # Output as markdown table
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

RESULTS_BASE = Path("/Users/ocuser/.openclaw/workspace/eval-results")
DASHBOARD_FILE = Path("/Users/ocuser/.openclaw/workspace/skills/agent-eval-framework/EVAL_RESULTS.md")


def load_results(timestamp_dir: Optional[str] = None) -> dict:
    """Load results from a specific timestamp directory or latest."""
    if timestamp_dir:
        results_path = RESULTS_BASE / timestamp_dir / "results.json"
    else:
        # Find latest results directory
        dirs = sorted(RESULTS_BASE.glob("*"), reverse=True)
        if not dirs:
            print("No evaluation results found. Run run-eval.sh first.")
            sys.exit(1)
        results_path = dirs[0] / "results.json"
    
    with open(results_path) as f:
        return json.load(f)


def calculate_trend(days: int = 7) -> List[dict]:
    """Calculate reliability trend over the last N days."""
    cutoff = datetime.now() - timedelta(days=days)
    trends = []
    
    for dir_path in sorted(RESULTS_BASE.glob("*")):
        try:
            dir_timestamp = datetime.strptime(dir_path.name, "%Y%m%d-%H%M%S")
            if dir_timestamp < cutoff:
                continue
            
            results_path = dir_path / "results.json"
            if not results_path.exists():
                continue
            
            with open(results_path) as f:
                data = json.load(f)
            
            trends.append({
                'timestamp': dir_timestamp,
                'reliability': data['overall_reliability'],
                'passed': data['passed'],
                'total': data['total_tests']
            })
        except (ValueError, KeyError):
            continue
    
    return trends


def generate_dashboard(data: dict, trend_data: Optional[List[dict]] = None) -> str:
    """Generate markdown dashboard."""
    dashboard = []
    dashboard.append("# OpenClaw Agent Evaluation Dashboard")
    dashboard.append("")
    dashboard.append(f"**Last Updated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    dashboard.append(f"**Last Run:** {data['timestamp']}")
    dashboard.append(f"**Mode:** {data['mode']}")
    dashboard.append("")
    
    # Overall metrics
    dashboard.append("## Overall Reliability")
    dashboard.append("")
    reliability_pct = data['overall_reliability'] * 100
    status_icon = "✅" if reliability_pct >= 90 else "⚠️" if reliability_pct >= 70 else "❌"
    dashboard.append(f"| Metric | Target | Current | Status |")
    dashboard.append(f"|--------|--------|---------|--------|")
    dashboard.append(f"| **Overall Reliability** | ≥90% | {reliability_pct:.1f}% | {status_icon} |")
    dashboard.append("")
    
    # Category breakdown
    dashboard.append("## Category Breakdown")
    dashboard.append("")
    dashboard.append("| Category | Passed | Total | Reliability | Status |")
    dashboard.append("|----------|--------|-------|-------------|--------|")
    
    category_targets = {
        'memory_recall': 0.95,
        'tool_routing': 0.90,
        'session_management': 0.95,
        'config_gateway': 1.00,
        'skill_execution': 0.90,
        'safety_governance': 1.00,
        'context_pipeline': 0.95
    }
    
    for cat, stats in sorted(data['category_stats'].items()):
        reliability = stats['passed'] / stats['total'] if stats['total'] > 0 else 0
        target = category_targets.get(cat, 0.90)
        icon = "✅" if reliability >= target else "⚠️"
        dashboard.append(f"| {cat.replace('_', ' ').title()} | {stats['passed']} | {stats['total']} | {reliability*100:.1f}% | {icon} |")
    
    dashboard.append("")
    
    # Trend chart (text-based)
    if trend_data and len(trend_data) > 1:
        dashboard.append("## 7-Day Trend")
        dashboard.append("")
        dashboard.append("```")
        for point in trend_data[-14:]:  # Last 14 runs
            bar_len = int(point['reliability'] * 50)
            bar = "█" * bar_len + "░" * (50 - bar_len)
            ts = point['timestamp'].strftime('%m/%d %H:%M')
            dashboard.append(f"{ts} │{bar}│ {point['reliability']*100:5.1f}%")
        dashboard.append("```")
        dashboard.append("")
    
    # Recent failures
    failures = [r for r in data['results'] if not r['passed']]
    if failures:
        dashboard.append("## Failed Tests (Action Required)")
        dashboard.append("")
        dashboard.append("| ID | Name | Category | Details |")
        dashboard.append("|----|------|----------|---------|")
        for f in failures[:10]:  # Show first 10
            details = f.get('details', {}).get('error', 'See results.json')
            dashboard.append(f"| {f['id']} | {f['name']} | {f['category']} | {details[:50]}... |")
        dashboard.append("")
    
    return "\n".join(dashboard)


def main():
    parser = argparse.ArgumentParser(description="Analyze OpenClaw agent evaluation results")
    parser.add_argument("--trend", type=str, help="Show trend over N days (e.g., '7d')")
    parser.add_argument("--min-reliability", type=float, help="Minimum reliability threshold (exit 1 if below)")
    parser.add_argument("--output", choices=["console", "markdown"], default="console", help="Output format")
    parser.add_argument("--timestamp", type=str, help="Specific timestamp directory to analyze")
    
    args = parser.parse_args()
    
    # Load results
    data = load_results(args.timestamp)
    
    # Calculate trend if requested
    trend_data = None
    if args.trend:
        days = int(args.trend.rstrip('d'))
        trend_data = calculate_trend(days)
    
    # Generate output
    if args.output == "markdown":
        dashboard = generate_dashboard(data, trend_data)
        print(dashboard)
        
        # Also write to dashboard file
        with open(DASHBOARD_FILE, 'w') as f:
            f.write(dashboard)
        print(f"\nDashboard written to: {DASHBOARD_FILE}", file=sys.stderr)
    else:
        # Console summary
        print(f"=== OpenClaw Agent Evaluation Results ===")
        print(f"Timestamp: {data['timestamp']}")
        print(f"Mode: {data['mode']}")
        print(f"Overall: {data['passed']}/{data['total_tests']} ({data['overall_reliability']*100:.1f}%)")
        print()
        print("By Category:")
        for cat, stats in sorted(data['category_stats'].items()):
            rel = stats['passed'] / stats['total'] * 100 if stats['total'] > 0 else 0
            print(f"  {cat.replace('_', ' ').title():20} {stats['passed']:3}/{stats['total']:3} ({rel:5.1f}%)")
        
        if trend_data:
            print(f"\nTrend (last {len(trend_data)} runs):")
            for point in trend_data[-7:]:
                ts = point['timestamp'].strftime('%m/%d %H:%M')
                print(f"  {ts}: {point['reliability']*100:.1f}%")
    
    # Check threshold
    if args.min_reliability is not None:
        if data['overall_reliability'] < args.min_reliability:
            print(f"\n❌ FAIL: Reliability ({data['overall_reliability']*100:.1f}%) below threshold ({args.min_reliability*100:.1f}%)", file=sys.stderr)
            sys.exit(1)
        else:
            print(f"\n✅ PASS: Reliability meets threshold", file=sys.stderr)


if __name__ == "__main__":
    main()
