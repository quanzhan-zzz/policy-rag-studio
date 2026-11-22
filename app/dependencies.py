from fastapi import Request

from app.services.task_publisher import TaskPublisher
from app.store import Store


def get_store(request: Request) -> Store:
    store = getattr(request.app.state, "store", None)
    if store is None:
        raise RuntimeError("应用尚未初始化数据存储")
    return store


def get_task_publisher(request: Request) -> TaskPublisher:
    publisher = getattr(request.app.state, "task_publisher", None)
    if publisher is None:
        raise RuntimeError("应用尚未初始化任务发布器")
    return publisher
