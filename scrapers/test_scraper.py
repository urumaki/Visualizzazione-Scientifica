import unittest

from scrape_modern import SEARCH_URL, fetch_tournament_links


class ModernScraperTest(unittest.TestCase):
    def test_collects_a_small_batch_of_tournaments(self):
        links = fetch_tournament_links(limit=10)
        self.assertEqual(len(links), 10)
        self.assertTrue(all(link.startswith("/tournament/") for link in links))
        self.assertIn("tournament_searches/create", SEARCH_URL)


if __name__ == "__main__":
    unittest.main()
