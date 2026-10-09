"""Persist page-level acquisition evidence beside Bronze rows."""


def save_capture_pages(conn, batch_id, pages, Jsonb):
    rows = [(batch_id, page["source_page"], page["response_sha256"], page["row_count"],
             Jsonb(page["response_metadata"]), Jsonb(page["technical_metadata"]))
            for page in pages]
    if rows:
        with conn.cursor() as cursor:
            cursor.executemany("""INSERT INTO bronze.capture_pages
                (batch_id, source_page, response_sha256, row_count,
                 response_metadata, technical_metadata)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (batch_id, source_page) DO NOTHING""", rows)


def backfill_capture_pages(conn, batch, Jsonb):
    pages = batch.get("capture_pages", [])
    if not pages:
        return
    batch_id = batch["manifest"]["batchId"]
    count = conn.execute("SELECT count(*) FROM bronze.capture_pages WHERE batch_id = %s",
                         (batch_id,)).fetchone()[0]
    if count not in (0, len(pages)):
        raise ValueError(f"Stored Bronze page metadata is incomplete: {batch_id}")
    if count == 0:
        save_capture_pages(conn, batch_id, pages, Jsonb)
