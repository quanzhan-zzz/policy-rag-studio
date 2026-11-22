from fastapi import Request

from app.store import Store


def get_store(request: Request) -> Store:
    store = getattr(request.app.state, "store", None)
    if store is None:
        raise RuntimeError("应用尚未初始化数据存储")
    return store
