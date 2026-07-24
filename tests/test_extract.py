import unittest

from scripts.extract_graph import clean_text, pattern_for

class ExtractTests(unittest.TestCase):
    def test_alias_boundaries_do_not_match_inside_words(self):
        ron = pattern_for(["Ron"])
        self.assertEqual(len(ron.findall("Ron met Hermione; ironically no one else.")), 1)

    def test_latin1_cleanup(self):
        self.assertIn("Harry", clean_text("Harry".encode("latin-1")))

if __name__ == "__main__":
    unittest.main()
