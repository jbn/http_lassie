import unittest
from http_lassie.worker_pool import *


class TestWorkerPool(unittest.TestCase):
    def test_cant_submit_none_sentinel(self):
        pool = WorkerPool(lambda x: x)
        with self.assertRaises(ValueError):
            pool.submit(None)

    def test_start_stop(self):
        def noop(item, submit):
            pass
        pool = WorkerPool(noop, auto_stop=True)
        pool.start()
        self.assertEqual(pool.stats(),
                         {'done_queue_empty': True,
                          'is_done': True,
                          'living_threads': 5,
                          'n_finished': 0,
                          'n_submitted': 0,
                          'work_queue_empty': True})
        pool.stop()
        self.assertEqual(pool.stats(),
                         {'done_queue_empty': True,
                          'is_done': True,
                          'living_threads': 0,
                          'n_finished': 0,
                          'n_submitted': 0,
                          'work_queue_empty': True})

    def test_integration(self):
        def err_callback(item, e, submit):
            self.assertEqual(item, 10)

        def f(x, submit):
            if x == 5:
                submit(100)
            elif x == 10:
                raise ValueError('Bad Value')
            return x**2

        pool = WorkerPool(f, err_callback, auto_stop=True)

        expected = set()
        for item in range(20):
            pool.submit(item)
            expected.add(item ** 2)

        expected.remove(10**2)  # Simulated error
        expected.add(100**2)  # Submitted while processing
        pool.start()
        collected = {item for item in pool.gather()}

        self.assertEqual(pool.stats(),
                         {'done_queue_empty': True,
                          'living_threads': 0,
                          'is_done': True,
                          'n_finished': 21,
                          'n_submitted': 21,
                          'work_queue_empty': True})
        self.assertEqual(len(expected), len(collected))
        self.assertEqual(expected, collected)

    def test_ignore(self):
        self.assertEqual(ignore(None, None, None), None)

    def test_error_in_error_handler(self):
        def task_func(item, callback):
            raise ValueError

        called = []
        def error_func(a, b, c):
            called.append(1)
            assert False

        pool = WorkerPool(task_func, error_func)
        pool.submit(10)
        pool.start()
        for item in pool.gather():
            pass
        self.assertEqual(called, [1])
        pool.stop()

if __name__ == '__main__':
    unittest.main()
