import threading
import time

from edit_episode_graph.backends._concurrency import BackendSemaphores


def test_caps_concurrency():
    sems = BackendSemaphores({"claude": 2})
    active = []
    peak = [0]
    lock = threading.Lock()

    def worker():
        with sems.acquire("claude"):
            with lock:
                active.append(1)
                peak[0] = max(peak[0], len(active))
            time.sleep(0.05)
            with lock:
                active.pop()

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert peak[0] == 2


def test_unknown_backend_unbounded():
    sems = BackendSemaphores({"claude": 2})
    with sems.acquire("never-heard-of-it"):
        pass  # no error
