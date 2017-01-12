from collections import Counter
import unittest
from http_lassie.user_agents import *


RARE = "Mozilla/5.0 (compatible; MSIE 9.0; Windows NT 6.0; Trident/5.0; Trident/5.0)"
POPULAR = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/601.6.17 (KHTML, like Gecko) Version/9.1.1 Safari/601.6.17"


class TestUserAgents(unittest.TestCase):
    def test_random_user_agent(self):
        # A Fragile test that relies upon known propabilities and the CDF
        # of the implied binomial distribution
        counts = Counter(random_user_agent() for _ in range(10000))
        self.assertLess(counts[RARE], 64.0)
        self.assertGreater(counts[RARE], 0)

        self.assertLess(counts[POPULAR], 1000)
        self.assertGreater(counts[POPULAR], 500)


if __name__ == '__main__':
    unittest.main()