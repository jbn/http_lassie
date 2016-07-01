from threading import Thread
try:
    from Queue import Queue
except ImportError:
    from queue import Queue


class WorkerPool:
    def __init__(self, task_func, n_workers=5, auto_stop=True):
        self._task_func = task_func
        self._auto_stop = True

        self._submitted = 0
        self._finished = 0
        self._work_queue = Queue()
        self._done_queue = Queue()

        self._workers = [Thread(target=self._work) for _ in range(n_workers)]

    def start(self):
        for worker in self._workers:
            worker.start()

    def stop(self):
        for worker in self._workers:
            self._work_queue.put(None)  # Signal end.

    def submit(self, item):
        self._submitted += 1
        self._work_queue.put(item)

    def gather(self):
        while not self.is_done() or not self._done_queue.empty():
            yield self._done_queue.get()
        if self._auto_stop:
            self.stop()

    def _work(self):
        while True:
            item = self._work_queue.get()
            if item is None:
                break

            try:
                self._done_queue.put(self._task_func(item, self.submit))
            except Exception as e:
                print("Exception {} on {}".format(e, item))
            finally:
                self._finished += 1

    def is_done(self):
        return self._submitted == self._finished and self._work_queue.empty()


