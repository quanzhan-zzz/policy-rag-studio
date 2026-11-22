import os

# Keep unit tests deterministic, database-free, and free of external API calls.
os.environ["APP_ENV"] = "test"
os.environ["STORE_BACKEND"] = "memory"
os.environ["EMBEDDING_PROVIDER"] = "hash"
os.environ["EMBEDDING_API_KEY"] = ""
os.environ["LLM_API_KEY"] = ""
