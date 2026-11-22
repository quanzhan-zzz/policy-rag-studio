import os

# Keep CI and local unit tests deterministic and free of external API calls.
# Real provider calls are exercised explicitly through integration commands.
os.environ["EMBEDDING_PROVIDER"] = "hash"
os.environ["EMBEDDING_API_KEY"] = ""
os.environ["LLM_API_KEY"] = ""
