import unittest

from scripts.extract_graph import add_graph_metrics, clean_text, pattern_for, sentiment_score

class ExtractTests(unittest.TestCase):
    def test_alias_boundaries_do_not_match_inside_words(self):
        ron = pattern_for(["Ron"])
        self.assertEqual(len(ron.findall("Ron met Hermione; ironically no one else.")), 1)

    def test_latin1_cleanup(self):
        self.assertIn("Harry", clean_text("Harry".encode("latin-1")))

    def test_sentiment_score_direction(self):
        self.assertGreater(sentiment_score("a good loyal friend smiled"), 0)
        self.assertLess(sentiment_score("a cruel evil attack caused pain"), 0)

    def test_graph_metrics(self):
        nodes = [{"id": name} for name in "ABC"]
        edges = [{"source": "A", "target": "B", "weight": 3},
                 {"source": "B", "target": "C", "weight": 2}]
        add_graph_metrics(nodes, edges)
        self.assertEqual(nodes[1]["degree"], 2)
        self.assertTrue(all("community" in node for node in nodes))

if __name__ == "__main__":
    unittest.main()
