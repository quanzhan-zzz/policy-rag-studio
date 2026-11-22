# Architecture Notes

## Runtime Shape

- `app/main.py`: FastAPI app and CORS
- `app/api/routes.py`: HTTP API
- `app/store.py`: `Store` interface and deterministic in-memory adapter
- `app/db/postgres.py`: PostgreSQL adapter for documents, chunks and traces
- `app/dependencies.py`: request-scoped repository access through application state
- `app/services/chunking.py`: fixed, heading and recursive chunkers
- `app/services/retrieval.py`: dense demo, BM25, RRF and heuristic reranking
- `app/services/evaluation.py`: Recall@5, MRR, nDCG@5 and P95 calculation
- `web/src/pages`: six-page React workbench
- `web/src/lib/api.ts`: typed API boundary

## Demo vs Production

The repository deliberately separates demo implementations from the public contract:

- The default hash embedding responds deterministically without model credentials.
- BGE-M3 and OpenAI-compatible embedding providers are selected through environment configuration.
- Heuristic reranking is local and reproducible.
- The API schemas already contain retrieval ranks, trace stages and citations.
- Documents, chunks and traces are persisted through the PostgreSQL adapter.
- Unit tests switch to the in-memory adapter with `STORE_BACKEND=memory`.

## Repository Seam

`app/store.py` defines the `Store` interface used by routes and services. Two adapters satisfy it:

- `InMemoryStore`: seeded deterministic data for unit tests and offline demos
- `PostgresStore`: documents, chunks and traces backed by SQLAlchemy async sessions

Repository contract tests run against both adapters. The PostgreSQL variant is enabled with
`TEST_DATABASE_URL`.

## Next Persistence Step

Add pgvector-backed chunk embeddings and Alembic migrations behind the existing Store seam. Dense
retrieval should consume stored vectors without changing the API response contract or frontend.
