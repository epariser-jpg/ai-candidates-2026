"""Pipeline for generating and storing embeddings for excerpts."""

from tqdm import tqdm

from src.db.init_db import get_connection, init_vec_table
from src.embeddings.local_embedder import embed_texts


def run_embed_pipeline(batch_size: int = 64) -> dict:
    """Generate embeddings for all excerpts that don't have them yet."""
    conn = get_connection()
    init_vec_table(conn)

    stats = {"embedded": 0, "skipped": 0, "errors": 0}

    # Get excerpts without embeddings
    rows = conn.execute("""
        SELECT e.id, e.excerpt_text, e.position_summary
        FROM excerpts e
        WHERE e.id NOT IN (SELECT excerpt_id FROM excerpt_embeddings)
        ORDER BY e.id
    """).fetchall()

    if not rows:
        print("No excerpts to embed.")
        conn.close()
        return stats

    print(f"Embedding {len(rows)} excerpts...")

    # Process in batches
    for i in tqdm(range(0, len(rows), batch_size), desc="Embedding"):
        batch = rows[i:i + batch_size]

        # Combine position summary and excerpt text for richer embeddings
        texts = []
        for row in batch:
            combined = f"{row['position_summary'] or ''} {row['excerpt_text']}"
            texts.append(combined.strip())

        try:
            embeddings = embed_texts(texts)
            for row, emb in zip(batch, embeddings):
                conn.execute(
                    "INSERT INTO excerpt_embeddings (excerpt_id, embedding) VALUES (?, ?)",
                    (row["id"], serialize_embedding(emb)),
                )
                stats["embedded"] += 1
        except Exception as e:
            stats["errors"] += len(batch)
            print(f"\n  Error embedding batch: {e}")

    conn.commit()

    print(f"\nEmbedding complete:")
    print(f"  Embedded: {stats['embedded']}")
    print(f"  Errors: {stats['errors']}")

    conn.close()
    return stats


def serialize_embedding(emb: list[float]) -> bytes:
    """Serialize embedding to bytes for sqlite-vec."""
    import struct
    return struct.pack(f"{len(emb)}f", *emb)
