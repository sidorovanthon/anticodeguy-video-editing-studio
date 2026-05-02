"""BackendRouter — selects the first available backend that satisfies node requirements.

Populated in v2 — see spec §7.4 (failover policy) and §7.5 (concurrency semaphores).
"""


class BackendRouter:
    def resolve(self, node):
        raise NotImplementedError("BackendRouter is implemented in v2 — see spec §7.")
