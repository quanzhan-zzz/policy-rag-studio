from typing import Protocol

from app.workers.celery_app import celery_app


class TaskPublisher(Protocol):
    def enqueue_index(self, task_id: str) -> None: ...


class CeleryTaskPublisher:
    def enqueue_index(self, task_id: str) -> None:
        celery_app.send_task("policyrag.index_document", args=[task_id])


class NoopTaskPublisher:
    def enqueue_index(self, task_id: str) -> None:
        return None
