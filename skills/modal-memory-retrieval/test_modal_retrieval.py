#!/usr/bin/env python3
"""
Test Suite for Modal Memory Retrieval

Tests modality detection, scoring, decay functions, and re-ranking.

Run: python test_modal_retrieval.py
"""

import unittest
from datetime import datetime, timedelta
from pathlib import Path

from modal_retrieval import (
    DEFAULT_CONFIG,
    detect_modality,
    extract_file_date,
    calculate_age_days,
    calculate_decay_factor,
    apply_modal_ranking,
)


class TestModalityDetection(unittest.TestCase):
    """Test modality detection from memory snippets."""
    
    def test_necessary_boundary_marker(self):
        """Detect necessary from [MODALITY: necessary] marker."""
        snippet = "[MODALITY: necessary] [KIND: boundary] Don't send external messages"
        result = detect_modality(snippet)
        self.assertEqual(result, 'necessary')
    
    def test_necessary_correction_marker(self):
        """Detect necessary from [KIND: correction] marker."""
        snippet = "[KIND: correction] Workspace path should be /Volumes/d03_ai"
        result = detect_modality(snippet)
        self.assertEqual(result, 'necessary')
    
    def test_necessary_keyword_boundary(self):
        """Detect necessary from 'boundary' keyword."""
        snippet = "Boundary: Never access external APIs without approval"
        result = detect_modality(snippet)
        self.assertEqual(result, 'necessary')
    
    def test_necessary_keyword_correction(self):
        """Detect necessary from 'correction' keyword."""
        snippet = "Correction: The timezone is America/Phoenix, not America/Los_Angeles"
        result = detect_modality(snippet)
        self.assertEqual(result, 'necessary')
    
    def test_necessary_keyword_invariant(self):
        """Detect necessary from 'invariant' keyword."""
        snippet = "This is an invariant property of the system"
        result = detect_modality(snippet)
        self.assertEqual(result, 'necessary')
    
    def test_contingent_framing_marker(self):
        """Detect contingent from [MODALITY: contingent] marker."""
        snippet = "[MODALITY: contingent] Focus on eval framework this session"
        result = detect_modality(snippet)
        self.assertEqual(result, 'contingent')
    
    def test_contingent_framing_change_kind(self):
        """Detect contingent from [KIND: framing_change] marker."""
        snippet = "[KIND: framing_change] Pause work on handoff generator"
        result = detect_modality(snippet)
        self.assertEqual(result, 'contingent')
    
    def test_contingent_keyword_framing(self):
        """Detect contingent from 'framing' keyword."""
        snippet = "Session framing: We're working on the plugin integration"
        result = detect_modality(snippet)
        self.assertEqual(result, 'contingent')
    
    def test_unknown_no_markers(self):
        """Return unknown when no markers present."""
        snippet = "User prefers direct communication style"
        result = detect_modality(snippet)
        self.assertEqual(result, 'unknown')
    
    def test_case_insensitive(self):
        """Detection should be case-insensitive."""
        snippet = "[modality: NECESSARY] BOUNDARY: Always ask first"
        result = detect_modality(snippet)
        self.assertEqual(result, 'necessary')


class TestFileDateExtraction(unittest.TestCase):
    """Test date extraction from memory file paths."""
    
    def test_dated_file(self):
        """Extract date from YYYY-MM-DD.md filename."""
        path = "memory/2026-07-07.md"
        result = extract_file_date(path)
        self.assertEqual(result, datetime(2026, 7, 7))
    
    def test_numbered_evergreen_file(self):
        """Return None for numbered evergreen files."""
        path = "memory/00-core-identity.md"
        result = extract_file_date(path)
        self.assertIsNone(result)
    
    def test_named_evergreen_file(self):
        """Return None for MEMORY.md."""
        path = "memory/MEMORY.md"
        result = extract_file_date(path)
        self.assertIsNone(result)
    
    def test_corrections_log(self):
        """Return None for corrections-log.md."""
        path = "memory/corrections-log.md"
        result = extract_file_date(path)
        self.assertIsNone(result)


class TestAgeCalculation(unittest.TestCase):
    """Test age calculation in days."""
    
    def test_recent_file(self):
        """Calculate age for recent file."""
        file_date = datetime.now() - timedelta(days=5)
        age = calculate_age_days(file_date)
        self.assertEqual(age, 5)
    
    def test_old_file(self):
        """Calculate age for old file."""
        file_date = datetime.now() - timedelta(days=60)
        age = calculate_age_days(file_date)
        self.assertEqual(age, 60)
    
    def test_evergreen_file(self):
        """Return None for evergreen files."""
        age = calculate_age_days(None)
        self.assertIsNone(age)


class TestDecayFactor(unittest.TestCase):
    """Test decay factor calculation for contingent items."""
    
    def test_no_decay_before_expiry(self):
        """No decay before expiry period."""
        factor = calculate_decay_factor(
            age_days=15,
            expiry_days=30,
            decay_rate=0.5,
            decay_function="linear"
        )
        self.assertEqual(factor, 1.0)
    
    def test_linear_decay_at_expiry(self):
        """Linear decay factor at expiry boundary."""
        factor = calculate_decay_factor(
            age_days=30,
            expiry_days=30,
            decay_rate=0.5,
            decay_function="linear"
        )
        self.assertEqual(factor, 1.0)
    
    def test_linear_decay_after_expiry(self):
        """Linear decay after expiry period."""
        # 60 days old, 30 day expiry = 30 days past expiry
        # After expiry_days past expiry, should be at minimum decay_rate
        factor = calculate_decay_factor(
            age_days=60,
            expiry_days=30,
            decay_rate=0.5,
            decay_function="linear"
        )
        self.assertAlmostEqual(factor, 0.5, places=2)
    
    def test_exponential_decay(self):
        """Exponential decay with half-life."""
        # After one half-life past expiry, should be at 50%
        factor = calculate_decay_factor(
            age_days=60,  # 30 days past 30-day expiry
            expiry_days=30,
            decay_rate=0.5,
            decay_function="exponential"
        )
        self.assertAlmostEqual(factor, 0.5, places=2)
    
    def test_evergreen_no_decay(self):
        """Evergreen files don't decay."""
        factor = calculate_decay_factor(
            age_days=None,
            expiry_days=30,
            decay_rate=0.5,
            decay_function="linear"
        )
        self.assertEqual(factor, 1.0)
    
    def test_max_decay_floor(self):
        """Decay doesn't go below minimum rate."""
        factor = calculate_decay_factor(
            age_days=365,  # Very old
            expiry_days=30,
            decay_rate=0.5,
            decay_function="exponential"
        )
        self.assertGreaterEqual(factor, 0.5)


class TestModalRanking(unittest.TestCase):
    """Test full modal ranking pipeline."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_results = [
            {
                'path': 'memory/2026-07-07.md',
                'score': 0.70,
                'snippet': '[MODALITY: necessary] Boundary: Don\'t send messages',
            },
            {
                'path': 'memory/2026-06-01.md',
                'score': 0.80,
                'snippet': '[MODALITY: contingent] Framing: Work on eval framework',
            },
            {
                'path': 'memory/00-core-identity.md',
                'score': 0.75,
                'snippet': 'User prefers expert terminology',
            },
        ]
    
    def test_necessary_boost_applied(self):
        """Necessary items get boosted."""
        results = apply_modal_ranking(self.test_results)
        necessary_item = results[0]  # Should be re-ranked to top
        
        self.assertEqual(necessary_item['modality'], 'necessary')
        self.assertGreater(necessary_item['capped_score'], necessary_item['score'])
    
    def test_contingent_decay_applied(self):
        """Old contingent items get decayed."""
        config = {
            **DEFAULT_CONFIG,
            'contingent_expiry_days': 30,
        }
        results = apply_modal_ranking(self.test_results, config)
        
        contingent_item = next(r for r in results if r['modality'] == 'contingent')
        self.assertLess(contingent_item['adjustment_factor'], 1.0)
    
    def test_unknown_unchanged(self):
        """Unknown modality items unchanged."""
        results = apply_modal_ranking(self.test_results)
        
        unknown_item = next(r for r in results if r['modality'] == 'unknown')
        self.assertEqual(unknown_item['adjustment_factor'], 1.0)
        self.assertAlmostEqual(
            unknown_item['capped_score'],
            unknown_item['score'],
            places=5
        )
    
    def test_re_ranking_by_adjusted_score(self):
        """Results re-ranked by adjusted score."""
        results = apply_modal_ranking(self.test_results)
        
        # Check that ranks are sequential
        for i, result in enumerate(results):
            self.assertEqual(result['rank'], i + 1)
        
        # Check that scores are in descending order
        scores = [r['capped_score'] for r in results]
        self.assertEqual(scores, sorted(scores, reverse=True))
    
    def test_score_capping(self):
        """Scores capped at maximum."""
        config = {
            **DEFAULT_CONFIG,
            'necessary_boost_cap': 1.0,
        }
        results = apply_modal_ranking(self.test_results, config)
        
        for result in results:
            self.assertLessEqual(result['capped_score'], 1.0)
    
    def test_preserve_original_fields(self):
        """Original result fields preserved."""
        results = apply_modal_ranking(self.test_results)
        
        for result in results:
            self.assertIn('path', result)
            self.assertIn('score', result)
            self.assertIn('snippet', result)
            # New fields added
            self.assertIn('modality', result)
            self.assertIn('adjusted_score', result)
            self.assertIn('rank', result)


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and error handling."""
    
    def test_empty_results(self):
        """Handle empty result list."""
        results = apply_modal_ranking([])
        self.assertEqual(len(results), 0)
    
    def test_missing_snippet(self):
        """Handle missing snippet field."""
        test_results = [{'path': 'memory/test.md', 'score': 0.5}]
        results = apply_modal_ranking(test_results)
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['modality'], 'unknown')
    
    def test_missing_score(self):
        """Handle missing score field."""
        test_results = [{'path': 'memory/test.md', 'snippet': 'test'}]
        results = apply_modal_ranking(test_results)
        
        self.assertEqual(len(results), 1)
        # Score should default to 0.0 even if missing from input
        self.assertIn('score', results[0])
        self.assertEqual(results[0]['score'], 0.0)
    
    def test_very_old_contingent_item(self):
        """Very old contingent items still have non-zero score."""
        old_date = datetime.now() - timedelta(days=365)
        test_results = [{
            'path': f'memory/{old_date.strftime("%Y-%m-%d")}.md',
            'score': 0.9,
            'snippet': '[MODALITY: contingent] Old framing change',
        }]
        
        results = apply_modal_ranking(test_results)
        
        # Should still have some score (not zeroed out)
        self.assertGreater(results[0]['capped_score'], 0.0)
        # Should be significantly reduced
        self.assertLess(results[0]['capped_score'], 0.5)


if __name__ == '__main__':
    unittest.main(verbosity=2)
