import unittest

from scripts.entry_definitions import entry_ids, get_entry


class EntryDefinitionTests(unittest.TestCase):
    def test_has_exactly_three_user_facing_entries(self):
        self.assertEqual(entry_ids(), ("return_day", "best_today", "future_us"))
        self.assertEqual(get_entry("return_day")["label"], "回到那一天")
        self.assertEqual(get_entry("best_today")["label"], "最好的今天")
        self.assertEqual(get_entry("future_us")["label"], "后来的我们")

    def test_every_question_explains_why_and_entry_never_exceeds_three(self):
        for entry_id in entry_ids():
            entry = get_entry(entry_id)
            self.assertLessEqual(len(entry["questions"]), 3)
            self.assertTrue(entry["anchor_prompt"].strip())
            for question in entry["questions"]:
                self.assertTrue(question["why"].strip())

    def test_only_future_entry_allows_simulation(self):
        self.assertFalse(get_entry("return_day")["allows_simulation"])
        self.assertFalse(get_entry("best_today")["allows_simulation"])
        self.assertTrue(get_entry("future_us")["allows_simulation"])
