# FastAPI backend — Architecture

> This document covers the legacy FastAPI v0 backend.  
> For the current Litestar v2 backend: [litestar/architecture.md](../litestar/architecture.md)

## Status

`CRUD_ACCESS` and `API_EXCLUDED_FIELDS` apply identically to both backends —
see [crud-access.md](../crud-access.md).

The FastAPI runtime (`half_orm_gen/backend/fastapi/v0/runtime.py`) does
**not** yet execute `@ho_api_filter` or `@ho_api_role` — that wiring exists
only in the Litestar runtime
(`half_orm_gen/backend/litestar/v2/runtime.py`). If your app relies on named
row filters or dynamic roles, use `--litestar` for now. This page will cover
the FastAPI request-handling internals once that parity lands; until then,
[litestar/architecture.md](../litestar/architecture.md) describes the
equivalent concepts for the backend that does support them.
