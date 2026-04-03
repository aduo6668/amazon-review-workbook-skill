from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from amazon_review_workbook import (
    DEFAULT_KEYWORDS,
    build_keyword_tuning_state,
    build_keyword_profile,
    extract_page_totals,
    resolve_keyword_plan,
    score_keyword_stats,
    should_skip_keyword,
)
from label_workflow import heuristic_category
from review_delivery_schema import DELIVERY_COLUMNS, normalize_categories


class ReviewWorkbookContractTests(unittest.TestCase):
    def test_delivery_schema_is_14_columns_with_username(self) -> None:
        self.assertEqual(len(DELIVERY_COLUMNS), 14)
        self.assertEqual(DELIVERY_COLUMNS[1], "评论用户名")

    def test_category_aliases_normalize_to_correct_spelling(self) -> None:
        self.assertEqual(normalize_categories("Product praise"), "Praise on product")
        self.assertEqual(normalize_categories("Priase on product"), "Praise on product")

    def test_positive_heuristic_uses_allowed_category(self) -> None:
        category, confident = heuristic_category("great quality and easy install", "5")
        self.assertTrue(confident)
        self.assertEqual(category, "Praise on product")

    def test_keyword_plan_is_manual_by_default(self) -> None:
        keywords, mode = resolve_keyword_plan(None, "electronics")
        self.assertEqual(keywords, [])
        self.assertEqual(mode, "off")

    def test_keyword_plan_supports_default_high_yield_preset(self) -> None:
        keywords, mode = resolve_keyword_plan([], "electronics")
        self.assertEqual(mode, "profile:electronics:tuned")
        self.assertEqual(keywords, DEFAULT_KEYWORDS[:12])

    def test_keyword_plan_preserves_explicit_values(self) -> None:
        keywords, mode = resolve_keyword_plan(
            ["quality", "refund", "quality"], "dashcam"
        )
        self.assertEqual(mode, "custom")
        self.assertEqual(keywords, ["quality", "refund"])

    def test_dashcam_profile_contains_universal_and_scene_terms(self) -> None:
        keywords = build_keyword_profile("dashcam")
        self.assertIn("quality", keywords)
        self.assertIn("app", keywords)
        self.assertIn("night", keywords)

    def test_extract_page_totals_distinguishes_reviews_and_ratings(self) -> None:
        totals = extract_page_totals(
            [
                "Showing 1-10 of 381 reviews",
                "2,145 global ratings",
            ]
        )
        self.assertEqual(totals["page_total_reviews"], 381)
        self.assertEqual(totals["page_total_ratings"], 2145)

    def test_score_keyword_stats_prefers_keywords_with_real_hits(self) -> None:
        hot = score_keyword_stats(
            {
                "best_new_count": 20,
                "total_new_count": 25,
                "positive_runs": 2,
                "zero_runs": 0,
                "total_runs": 2,
            }
        )
        cold = score_keyword_stats(
            {
                "best_new_count": 0,
                "total_new_count": 0,
                "positive_runs": 0,
                "zero_runs": 3,
                "total_runs": 3,
            }
        )
        self.assertGreater(hot, cold)

    def test_skip_keyword_when_history_has_positive_hits(self) -> None:
        should_skip, reason = should_skip_keyword(
            {
                "best_new_count": 5,
                "searched_at": "2026-04-03T00:00:00.000000Z",
            },
            reuse_scope="successful",
            zero_result_retry_hours=72,
        )
        self.assertTrue(should_skip)
        self.assertEqual(reason, "successful_history")

    def test_skip_recent_zero_result_keyword_temporarily(self) -> None:
        searched_at = (
            datetime.now(timezone.utc) - timedelta(hours=12)
        ).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        should_skip, reason = should_skip_keyword(
            {
                "best_new_count": 0,
                "searched_at": searched_at,
            },
            reuse_scope="successful",
            zero_result_retry_hours=72,
        )
        self.assertTrue(should_skip)
        self.assertEqual(reason, "recent_zero_history")

    def test_keyword_tuning_state_prefers_high_yield_terms(self) -> None:
        payload = build_keyword_tuning_state(
            keyword_stats={
                "quality": {
                    "keyword": "quality",
                    "best_new_count": 0,
                    "total_new_count": 0,
                    "positive_runs": 0,
                    "zero_runs": 2,
                    "total_runs": 2,
                },
                "install": {
                    "keyword": "install",
                    "best_new_count": 4,
                    "total_new_count": 4,
                    "positive_runs": 1,
                    "zero_runs": 0,
                    "total_runs": 1,
                },
                "video": {
                    "keyword": "video",
                    "best_new_count": 23,
                    "total_new_count": 23,
                    "positive_runs": 1,
                    "zero_runs": 0,
                    "total_runs": 1,
                },
            },
            top_k=5,
        )
        dashcam_keywords = payload["profiles"]["dashcam"]["recommended_keywords"]
        self.assertEqual(dashcam_keywords[0], "video")
        self.assertIn("install", dashcam_keywords)


if __name__ == "__main__":
    unittest.main()
