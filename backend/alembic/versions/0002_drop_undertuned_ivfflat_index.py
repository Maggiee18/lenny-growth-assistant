"""drop under-tuned ivfflat index -- exact search at this dataset scale

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-14

Found live: an ivfflat index with lists=100 against a ~1,455-row
transcript_chunks table causes IVFFlat's approximate search (default
probes=1) to occasionally probe a near-empty or empty list for a given
query vector and return literally ZERO candidate rows -- not a relevance
miss, a hard retrieval bug (confirmed via EXPLAIN: the planner uses the
index for the exact ORDER BY ... LIMIT pattern retrieval.py issues, and the
row count returned was reproducibly 0 for a specific real query while an
identically-shaped query for different text returned 10).

pgvector's own sizing guidance is roughly `lists = rows / 1000` for typical
workloads -- 100 lists for ~1,500 rows is drastically over-provisioned.
Given this project's expected scale (PRD.md: "tens to low hundreds of
episodes, thousands of chunks"), the simplest and most correct fix is to
drop the approximate index entirely and let pgvector do an exact sequential
cosine-distance scan, which is both fast enough at this size (sub-10ms) and
can never silently miss a real match. If the corpus grows into the 100K+
row range, a properly-tuned ivfflat (`lists = rows/1000`, higher `probes`)
or an HNSW index should be reconsidered -- see architecture.md "Retrieval
flow" for this trade-off.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_transcript_chunks_embedding")


def downgrade() -> None:
    op.execute(
        "CREATE INDEX ix_transcript_chunks_embedding ON transcript_chunks "
        "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )
