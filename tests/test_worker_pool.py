import unittest
from http_lassie.worker_pool import *


class TestWorkerPool(unittest.TestCase):
    def test_cant_submit_none_sentinel(self):
        pool = WorkerPool(lambda x: x)
        with self.assertRaises(ValueError):
            pool.submit(None)

    def test_integration(self):
        def err_callback(item, e, submit):
            self.assertEqual(item, 10)

        def f(x, submit):
            if x == 5:
                submit(100)
            elif x == 10:
                raise ValueError('Bad Value')
            return x**2

        pool = WorkerPool(f, err_callback)

        expected = set()
        for item in range(20):
            pool.submit(item)
            expected.add(item ** 2)

        expected.remove(10**2)  # Simulated error
        expected.add(100**2)  # Submitted while processing

        pool.start()
        collected = {item for item in pool.gather()}
        self.assertEqual(expected, collected)


if __name__ == '__main__':
    unittest.main()