import asyncio
import logging

from app.config import get_settings
from app.db.postgres import PostgresStore
from app.schemas import IndexTaskStatus
from app.services.indexing import execute_index_task
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _run_index_task(task_id: str):
    settings = get_settings()
    store = await PostgresStore.create(
        settings.database_url,
        seed_demo_data=False,
    )
    try:
        task = await execute_index_task(
            store,
            task_id,
            stale_after_seconds=settings.index_task_stale_seconds,
        )
        logger.info("Index task %s finished with status %s", task_id, task.status if task else None)
        return task
    finally:
        await store.close()


@celery_app.task(
    bind=True,
    name="policyrag.index_document",
    max_retries=3,
)
def index_document(self, task_id: str) -> None:
    task = asyncio.run(_run_index_task(task_id))
    if task is not None and task.status in {
        IndexTaskStatus.PARSING,
        IndexTaskStatus.CHUNKING,
        IndexTaskStatus.EMBEDDING,
    }:
        settings = get_settings()
        raise self.retry(countdown=settings.index_task_stale_seconds + 5)


async def _recover_stale_tasks() -> None:
    settings = get_settings()
    store = await PostgresStore.create(
        settings.database_url,
        seed_demo_data=False,
    )
    try:
        stale = await store.list_stale_index_tasks(settings.index_task_stale_seconds)
        for task in stale:
            logger.info("Requeueing stale index task %s at %s", task.id, task.status)
            celery_app.send_task("policyrag.index_document", args=[task.id])
    finally:
        await store.close()


@celery_app.task(name="policyrag.recover_stale_tasks")
def recover_stale_tasks() -> None:
    asyncio.run(_recover_stale_tasks())
