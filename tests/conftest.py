import os

# Keep unit tests deterministic, database-free, and free of external API calls.
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("STORE_BACKEND", "memory")
os.environ.setdefault("EMBEDDING_PROVIDER", "hash")
os.environ.setdefault("EMBEDDING_DIMENSIONS", "192")
os.environ.setdefault("HASH_EMBEDDING_DIMENSIONS", "192")
os.environ["EMBEDDING_API_KEY"] = ""
os.environ["LLM_API_KEY"] = ""
