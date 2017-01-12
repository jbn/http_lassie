from threading import Thread
from six.moves.queue import Queue


class WorkerPool:
    def __init__(self, task_func, n_workers=5, auto_stop=True):
        """
        Create a worker pool.

        :param task_func: a function with the signature of f(item, submit),
            where submit is the bound `.submit` method of the instantiated
            class (allowing resubmission)
        :param n_workers: number of simultaneous workers (Threaded)
        :param auto_stop: if True, kill each worker in the pool when there
            are no items left to process or items still in processing
        """
        self._task_func = task_func
        self._auto_stop = True

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
        """
        for worker in self._workers:
            self._work_queue.put(None)  # Signal end.

    def submit(self, item):
        """
        Submit some item for processing.
        """
        assert item is not None, "Can't submit a None -- it's the kill value"
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
                # TODO: Use exception queue and on_error
                print("Exception {} on {}".format(e, item))
            finally:
                self._finished += 1

    def is_done(self):
        return self._submitted == self._finished and self._work_queue.empty()


