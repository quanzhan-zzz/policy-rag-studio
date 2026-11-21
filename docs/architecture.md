# Architecture Notes

## Runtime Shape

- `app/main.py`: FastAPI app and CORS
- `app/api/routes.py`: HTTP API
- `app/store.py`: in-memory repository shaped like a future PostgreSQL repository
- `app/services/chunking.py`: fixed, heading and recursive chunkers
- `app/services/retrieval.py`: dense demo, BM25, RRF and heuristic reranking
- `app/services/evaluation.py`: Recall@5, MRR, nDCG@5 and P95 calculation
- `web/src/pages`: six-page React workbench
- `web/src/lib/api.ts`: typed API boundary

## Demo vs Production

The repository deliberately separates demo implementations from the public contract:

- Hash embedding responds deterministically without model credentials.
- Heuristic reranking is local and reproducible.
- The API schemas already contain retrieval ranks, trace stages and citations.

Replacing these adapters with BGE-M3 and BGE Reranker should not require UI changes.

## Next Persistence Step

Move the repository behind an interface:

```python
class DocumentRepository(Protocol):
    async def list_documents(self) -> list[DocumentSummary]: ...
    async def list_chunks(self, document_id: str, strategy: ChunkStrategy) -> list[ChunkRecord]: ...
```

Then implement `PostgresDocumentRepository` with pgvector and keep `InMemoryDocumentRepository` for tests.
