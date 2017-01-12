import unittest
from http_lassie.worker_pool import *


class TestWorkerQueue(unittest.TestCase):
    def test_integration(self):
        pool = WorkerPool(lambda x, _: x**2)

        expected = set()
        for item in range(20):
            pool.submit(item)
            expected.add(item ** 2)

        pool.start()
        collected = {item for item in pool.gather()}
        self.assertEqual(expected, collected)


if __name__ == '__main__':
    unittest.main()