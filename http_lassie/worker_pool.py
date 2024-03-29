import logging
import sys
from threading import Thread, Lock
from six.moves.queue import Queue
from http_lassie.smart_fetcher import format_exception


def ignore(item, error, submit):
    pass


def echo_error(item, error, submit):
    logging.error(format_exception("[_work]", 0, sys.exc_info()))


class WorkerPool:
    def __init__(self, task_func, error_func=echo_error, n_workers=5,
                 auto_stop=True):
        """
        Create a worker pool.

        :param task_func: a function with the signature of f(item, submit),
            where submit is the bound `.submit` method of the instantiated
            class (allowing resubmission)
        :param error_func: a function with the signature of
            f(item, exception, submit) that gets called on any exception
            not handled by the task_func
        :param n_workers: number of simultaneous workers (Threaded)
        :param auto_stop: if True, kill each worker in the pool when there
            are no items left to process or items still in processing
        """
        self._lock = Lock()
        self._task_func = task_func
        self._error_func = error_func
        self._auto_stop = auto_stop

        self._submitted = 0
        self._finished = 0
        self._work_queue = Queue()
        self._done_queue = Queue()

        self._workers = [Thread(target=self._work) for _ in range(n_workers)]

    def start(self):
        """
        Start each thread and begin processing the queue.
        """
        for worker in self._workers:
            worker.start()

    def stop(self):
        """
        Send each thread the kill sentinel.

        This is a graceful stop. The method then blocks until all threads die.
        """
        for worker in self._workers:
            self._work_queue.put(None)  # Signal end.

        for worker in self._workers:
            worker.join()

    def submit(self, item):
        """
        Submit some item for processing.
        """
        if item is None:
            raise ValueError("Can't submit a `None`. It's the kill sentinel")

        with self._lock:
            self._submitted += 1
        self._work_queue.put(item)

    def gather(self):
        """
        Yields an item from the done queue otherwise blocks.

        If auto_stop is True, this will automatically call stop when there
        is nothing left to process.

        :return: an item from the done queue
        """
        while not self.is_done() or not self._done_queue.empty():
            yield self._done_queue.get()

        if self._auto_stop:
            self.stop()

    def _work(self):
        while True:
            item = self._work_queue.get()
            if item is None:  # Kill sentinel
                break

            try:
                self._done_queue.put(self._task_func(item, self.submit))
            except Exception as e:
                try:
                    self._error_func(item, e, self.submit)
                except Exception as e:
                    print(format_exception("[_work]", 0, sys.exc_info()))
            finally:
                with self._lock:
                    self._finished += 1

    def is_done(self):
        return self._submitted == self._finished and self._work_queue.empty()

    def stats(self):
        with self._lock:
            return {'n_submitted': self._submitted,
                    'n_finished': self._finished,
                    'work_queue_empty': self._work_queue.empty(),
                    'done_queue_empty': self._done_queue.empty(),
                    'living_threads': sum(t.is_alive() for t in self._workers),
                    'is_done': self.is_done()}
