import unittest

from scripts.semantic_records import next_revision, validate_semantic_record_graph


def record(record_id, layer, **overrides):
    value = {
        "id": record_id,
        "semantic_layer": layer,
        "text": "测试文本",
        "source_refs": ["src_note_001"],
        "status": "user_confirmed",
        "confidence": 0.8,
        "sensitivity": "low",
        "visibility": "private",
        "created_at": "2026-07-17T00:00:00Z",
        "revision": 1,
    }
    value.update(overrides)
    return value


class SemanticRecordTests(unittest.TestCase):
    def test_accepts_confirmed_understanding_with_simulation_origin(self):
        records = [
            record("rec_fact_a", "fact"),
            record("rec_sim_a", "simulation", status="inferred", base_record_ids=["rec_fact_a"]),
            record("rec_understanding_a", "understanding", simulation_origin_id="rec_sim_a"),
        ]
        self.assertEqual(validate_semantic_record_graph(records), [])

    def test_rejects_simulation_origin_on_fact(self):
        records = [
            record("rec_fact_b", "fact"),
            record("rec_sim_a", "simulation", status="inferred", base_record_ids=["rec_fact_b"]),
            record("rec_fact_a", "fact", simulation_origin_id="rec_sim_a"),
        ]
        self.assertIn("cannot reference simulation_origin_id", validate_semantic_record_graph(records)[0])

    def test_rejects_automatic_understanding_from_simulation(self):
        records = [
            record("rec_fact_a", "fact"),
            record("rec_sim_a", "simulation", status="inferred", base_record_ids=["rec_fact_a"]),
            record("rec_understanding_a", "understanding", status="inferred", simulation_origin_id="rec_sim_a"),
        ]
        self.assertIn("must be user_confirmed", validate_semantic_record_graph(records)[0])

    def test_rejects_missing_simulation_base_record(self):
        records = [record("rec_sim_a", "simulation", status="inferred", base_record_ids=["rec_missing"])]
        self.assertIn("unknown base record", validate_semantic_record_graph(records)[0])

    def test_next_revision(self):
        self.assertEqual(next_revision({"revision": 4}), 5)

    def test_next_revision_rejects_zero(self):
        with self.assertRaises(ValueError):
            next_revision({"revision": 0})
