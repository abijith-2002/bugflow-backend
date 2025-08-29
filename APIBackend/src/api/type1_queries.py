from typing import List, Optional, Dict
from math import sqrt

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from supabase import Client as SupabaseClient
from rapidfuzz import fuzz

from .config import get_settings
from .supabase_client import SupabaseClientProvider

router = APIRouter(prefix="/query", tags=["Queries"])


def _get_supabase(settings=Depends(get_settings)) -> SupabaseClient:
    """PUBLIC_INTERFACE: Provide Supabase client from settings (shared helper)."""
    try:
        provider = SupabaseClientProvider(
            supabase_url=settings.SUPABASE_URL, supabase_key=settings.SUPABASE_ANON_KEY
        )
        return provider.client()
    except ValueError as e:
        raise HTTPException(status_code=500, detail=f"Configuration error: {str(e)}")


class ColumnInfo(BaseModel):
    """Model for a stored column and its optional embedding vector."""
    name: str = Field(..., description="Column name")
    table: Optional[str] = Field(default=None, description="Optional table name or context")
    embedding: Optional[List[float]] = Field(
        default=None, description="Precomputed embedding vector for the column name"
    )


class TechniqueScores(BaseModel):
    exact: float = Field(..., description="Exact match score in [0,1]")
    fuzzy: float = Field(..., description="Fuzzy string match score in [0,1] scaled from rapidfuzz ratio")
    semantic: float = Field(..., description="Cosine similarity score in [0,1] using embeddings (0 if no embedding)")


class RelevantColumn(BaseModel):
    column: ColumnInfo = Field(..., description="Matched column info")
    scores: TechniqueScores = Field(..., description="Scores per technique")
    combined_score: float = Field(..., description="Weighted combined score in [0,1]")


class Type1QueryRequest(BaseModel):
    """Payload for Type 1 relevant column matching query."""
    query: str = Field(..., description="User's query string to match against column names", min_length=1)
    top_k: Optional[int] = Field(default=5, description="Number of top columns to return (max 20)")
    project_id: Optional[str] = Field(
        default=None, description="Optional context to filter stored columns by project_id if your schema supports it"
    )


class Type1QueryResponse(BaseModel):
    """Response with top relevant columns and their scores."""
    query: str = Field(..., description="Original query string")
    results: List[RelevantColumn] = Field(..., description="Top relevant columns and scores")
    technique_weights: Dict[str, float] = Field(
        ..., description="Weights used to aggregate technique scores: exact, fuzzy, semantic"
    )


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    """Compute cosine similarity between two vectors. Returns 0.0 for invalid input."""
    if not a or not b:
        return 0.0
    if len(a) != len(b):
        return 0.0
    # Compute dot and norms
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na == 0.0 or nb == 0.0:
        return 0.0
    return max(0.0, min(1.0, dot / (sqrt(na) * sqrt(nb))))


def _normalize_score(v: float) -> float:
    """Clamp score to [0,1]."""
    return max(0.0, min(1.0, v))


def _exact_match_score(q: str, col_name: str) -> float:
    """Return 1.0 for case-insensitive exact match, else 0.0."""
    return 1.0 if q.strip().lower() == (col_name or "").strip().lower() else 0.0


def _fuzzy_match_score(q: str, col_name: str) -> float:
    """Scale rapidfuzz ratio (0..100) to [0,1]."""
    if not col_name:
        return 0.0
    return _normalize_score(fuzz.ratio(q, col_name) / 100.0)


def _aggregate_scores(exact: float, fuzzy: float, semantic: float) -> float:
    """
    Weighted aggregation of technique scores.
    Weights chosen to favor exact and semantic matches while keeping fuzzy informative.
    """
    w_exact = 0.5
    w_fuzzy = 0.2
    w_semantic = 0.3
    return _normalize_score(w_exact * exact + w_fuzzy * fuzzy + w_semantic * semantic)


async def _fetch_columns(supabase: SupabaseClient, project_id: Optional[str]) -> List[ColumnInfo]:
    """
    Fetch stored column names and embeddings from Supabase.
    Expected table: public.columns_catalog (suggested schema)
      - id: uuid
      - name: text
      - table: text (optional)
      - embedding: vector or float[] stored as JSON/array accessible via PostgREST
      - project_id: uuid (optional)
    This implementation is resilient: if table is missing or shape varies, returns empty list.
    """
    try:
        query = supabase.table("columns_catalog").select("name,table,embedding")
        if project_id:
            query = query.eq("project_id", project_id)
        resp = query.execute()
        rows = resp.data or []
        out: List[ColumnInfo] = []
        for r in rows:
            emb = r.get("embedding")
            # Normalize embedding to list[float] if present and iterable
            emb_list: Optional[List[float]] = None
            if isinstance(emb, list):
                try:
                    emb_list = [float(x) for x in emb]
                except Exception:
                    emb_list = None
            out.append(
                ColumnInfo(
                    name=str(r.get("name", "")),
                    table=r.get("table"),
                    embedding=emb_list,
                )
            )
        return out
    except Exception:
        # Silently degrade to no stored columns
        return []


# PUBLIC_INTERFACE
@router.post(
    "/type1",
    response_model=Type1QueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Relevant Column Matching (Type 1)",
    description=(
        "Given a query string, match it against stored column names using: "
        "(1) exact match, (2) fuzzy string match via rapidfuzz, and "
        "(3) semantic similarity using stored column embeddings (cosine similarity). "
        "Returns the top 5 most relevant columns by aggregated score."
    ),
    responses={
        200: {"description": "Top relevant columns returned"},
        400: {"description": "Validation error"},
        500: {"description": "Server or configuration error"},
    },
)
async def type1_relevant_columns(
    payload: Type1QueryRequest,
    supabase: SupabaseClient = Depends(_get_supabase),
) -> Type1QueryResponse:
    """
    PUBLIC_INTERFACE
    Endpoint to compute relevant columns for a Type 1 query.

    Parameters:
    - query: the text to match against column names.
    - top_k: number of top results to return (default 5, max 20).
    - project_id: optional filter if your storage segments columns by project.

    Returns:
    - A list of up to top_k relevant columns with individual technique scores and the combined score.
    """
    q = payload.query.strip()
    if not q:
        raise HTTPException(status_code=400, detail="Query must be a non-empty string")
    top_k = max(1, min(int(payload.top_k or 5), 20))

    # Fetch stored columns
    columns = await _fetch_columns(supabase, payload.project_id)

    # If no columns available, gracefully return empty results
    if not columns:
        return Type1QueryResponse(
            query=q,
            results=[],
            technique_weights={"exact": 0.5, "fuzzy": 0.2, "semantic": 0.3},
        )

    # Optional: compute query embedding if a query_embeddings table exists; otherwise rely on fuzzy/exact only
    # For this task, we assume embeddings for columns exist and we cannot compute on-the-fly;
    # we approximate semantic only when column.embedding is available and a query embedding is provided by storage.
    # Try fetching query embedding from a helper table if present (best-effort).
    query_emb: Optional[List[float]] = None
    try:
        # Optional helper table: public.query_embeddings with columns: query text primary key, embedding float[]
        resp = (
            supabase.table("query_embeddings")
            .select("embedding")
            .eq("query", q)
            .limit(1)
            .execute()
        )
        data = (resp.data or [])
        if data:
            emb_list = data[0].get("embedding")
            if isinstance(emb_list, list):
                query_emb = [float(x) for x in emb_list]
    except Exception:
        query_emb = None  # proceed without semantic if not available

    # Score each column
    scored: List[RelevantColumn] = []
    for col in columns:
        exact = _exact_match_score(q, col.name)
        fuzzy = _fuzzy_match_score(q, col.name)
        semantic = 0.0
        if query_emb and col.embedding:
            semantic = _normalize_score(_cosine_similarity(query_emb, col.embedding))
        scores = TechniqueScores(exact=exact, fuzzy=fuzzy, semantic=semantic)
        combined = _aggregate_scores(exact, fuzzy, semantic)
        scored.append(
            RelevantColumn(column=col, scores=scores, combined_score=combined)
        )

    # Rank and take top_k
    scored.sort(key=lambda x: x.combined_score, reverse=True)
    results = scored[:top_k]

    return Type1QueryResponse(
        query=q,
        results=results,
        technique_weights={"exact": 0.5, "fuzzy": 0.2, "semantic": 0.3},
    )
