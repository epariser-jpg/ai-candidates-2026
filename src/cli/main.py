"""CLI for the 2026 Candidates AI Positions Database."""

import asyncio
import csv
import sys
from pathlib import Path

import click

from src.config import DATABASE_PATH, PROJECT_ROOT
from src.db.init_db import init_db, get_connection


@click.group()
def cli():
    """2026 Candidates AI Positions Database."""
    pass


@cli.command()
def init():
    """Initialize the database."""
    conn = init_db()
    count = conn.execute("SELECT COUNT(*) as n FROM tags").fetchone()["n"]
    conn.close()
    click.echo(f"Database initialized at {DATABASE_PATH}")
    click.echo(f"  {count} tags seeded")


@cli.command()
@click.option("--office", type=click.Choice(["Senate", "House", "Governor"]), default="Senate")
@click.option("--discover-urls", is_flag=True, help="Attempt to discover campaign URLs (slow)")
@click.option("--manual-csv", type=click.Path(exists=True), help="Path to manual candidates CSV")
@click.option("--bulk", is_flag=True, help="Use FEC bulk data download (no rate limits)")
def roster(office, discover_urls, manual_csv, bulk):
    """Fetch and store candidate roster from FEC API."""
    from src.roster.roster_pipeline import run_roster_pipeline

    csv_path = Path(manual_csv) if manual_csv else None
    stats = asyncio.run(run_roster_pipeline(
        office=office,
        discover_urls=discover_urls,
        manual_csv=csv_path,
        use_bulk=bulk,
    ))
    click.echo(f"\nRoster pipeline complete: {stats}")


@cli.command(name="discover-urls")
@click.option("--delay", default=2.5, help="Delay between requests in seconds")
def discover_urls(delay):
    """Discover campaign website URLs from Ballotpedia for all 2026 Senate candidates."""
    from src.roster.ballotpedia import discover_all_senate_urls
    stats = asyncio.run(discover_all_senate_urls(delay=delay))
    click.echo(f"\nURL discovery complete: {stats}")


@cli.command()
@click.option("--office", type=click.Choice(["Senate", "House", "Governor"]), default=None)
@click.option("--state", default=None, help="Filter by state")
@click.option("--limit", default=None, type=int, help="Max candidates to scrape")
@click.option("--candidate-id", default=None, type=int, help="Scrape a specific candidate")
def scrape(office, state, limit, candidate_id):
    """Scrape campaign websites for candidates with URLs."""
    from src.scraper.scrape_pipeline import run_scrape_pipeline

    stats = asyncio.run(run_scrape_pipeline(
        office=office, state=state, limit=limit, candidate_id=candidate_id,
    ))
    click.echo(f"\nScrape complete: {stats}")


@cli.command()
@click.option("--office", type=click.Choice(["Senate", "House", "Governor"]), default=None)
@click.option("--state", default=None, help="Filter by state")
@click.option("--limit", default=None, type=int, help="Max content items to analyze")
@click.option("--candidate-id", default=None, type=int, help="Analyze a specific candidate")
@click.option("--reanalyze", is_flag=True, help="Re-analyze previously analyzed content")
@click.option("--model", default=None, help="Claude model to use")
def analyze(office, state, limit, candidate_id, reanalyze, model):
    """Analyze scraped content for AI-related positions using Claude."""
    from src.analysis.analysis_pipeline import run_analysis_pipeline
    from src.config import ANALYSIS_MODEL

    stats = asyncio.run(run_analysis_pipeline(
        office=office, state=state, limit=limit,
        candidate_id=candidate_id, reanalyze=reanalyze,
        model=model or ANALYSIS_MODEL,
    ))
    click.echo(f"\nAnalysis complete: {stats}")


@cli.command()
def embed():
    """Generate embeddings for all excerpts."""
    from src.embeddings.embed_pipeline import run_embed_pipeline
    stats = run_embed_pipeline()
    click.echo(f"\nEmbed complete: {stats}")


@cli.command()
@click.option("--text", "-t", default=None, help="Semantic search query")
@click.option("--tag", "-g", multiple=True, help="Filter by tag (can specify multiple)")
@click.option("--keyword", "-k", default=None, help="FTS keyword search")
@click.option("--office", type=click.Choice(["Senate", "House", "Governor"]), default=None)
@click.option("--state", default=None, help="Filter by state")
@click.option("--party", default=None, help="Filter by party")
@click.option("--sentiment", type=click.Choice(["supportive", "cautious", "opposed", "neutral", "mixed"]), default=None)
@click.option("--limit", default=20, help="Max results")
def search(text, tag, keyword, office, state, party, sentiment, limit):
    """Search the database using structured, keyword, or semantic search."""
    if not text and not tag and not keyword:
        click.echo("Provide at least one of: --text, --tag, or --keyword")
        return

    # Use structured search if only tags/sentiment specified
    if tag and not text and not keyword:
        from src.search.structured import search_by_tags
        results = search_by_tags(
            tags=list(tag), party=party, office=office,
            state=state, sentiment=sentiment, limit=limit,
        )
    # Use keyword search if only keyword specified
    elif keyword and not text and not tag:
        from src.search.fulltext import search_keyword
        results = search_keyword(keyword=keyword, office=office, state=state, party=party, limit=limit)
    # Use semantic search if only text specified
    elif text and not tag and not keyword:
        from src.search.semantic import search_semantic
        results = search_semantic(query=text, office=office, state=state, party=party, limit=limit)
    # Use hybrid search if multiple modes
    else:
        from src.search.hybrid import hybrid_search
        results = hybrid_search(
            query=text, tags=list(tag) if tag else None,
            keyword=keyword, office=office, state=state, party=party, limit=limit,
        )

    if not results:
        click.echo("No results found.")
        return

    for i, r in enumerate(results, 1):
        name = r.get("name", "Unknown")
        party_str = r.get("party", "")
        office_str = r.get("office", "")
        state_str = r.get("state", "")
        click.echo(f"\n{'='*70}")
        click.echo(f"#{i}  {name} ({party_str}) — {office_str}, {state_str}")

        if r.get("position_summary"):
            click.echo(f"  Position: {r['position_summary']}")
        if r.get("excerpt_text"):
            excerpt = r["excerpt_text"][:200]
            click.echo(f'  Excerpt: "{excerpt}..."' if len(r["excerpt_text"]) > 200 else f'  Excerpt: "{excerpt}"')
        if r.get("snippet"):
            click.echo(f"  Match: ...{r['snippet']}...")
        if r.get("tag_names"):
            click.echo(f"  Tags: {r['tag_names']}")
        if r.get("sentiment"):
            click.echo(f"  Sentiment: {r['sentiment']}")
        if r.get("similarity"):
            click.echo(f"  Similarity: {r['similarity']:.3f}")
        if r.get("source_url"):
            click.echo(f"  Source: {r['source_url']}")

    click.echo(f"\n{len(results)} results")


@cli.command()
@click.argument("candidate_names", nargs=-1)
@click.option("--tag", "-g", default=None, help="Compare on a specific tag")
def compare(candidate_names, tag):
    """Compare AI positions between candidates. Pass candidate names as arguments."""
    if len(candidate_names) < 2:
        click.echo("Provide at least 2 candidate names to compare.")
        return

    from src.search.structured import get_candidate_positions
    conn = get_connection()

    for name in candidate_names:
        # Fuzzy match candidate name
        row = conn.execute(
            "SELECT id, name, party, office, state FROM candidates WHERE name LIKE ? LIMIT 1",
            (f"%{name}%",),
        ).fetchone()

        if not row:
            click.echo(f"\nCandidate '{name}' not found.")
            continue

        click.echo(f"\n{'='*70}")
        click.echo(f"{row['name']} ({row['party']}) — {row['office']}, {row['state']}")
        click.echo(f"{'='*70}")

        positions = get_candidate_positions(row["id"])
        if not positions:
            click.echo("  No AI-related positions found.")
            continue

        for p in positions:
            if tag and tag not in (p.get("tag_names") or ""):
                continue
            click.echo(f"\n  [{p.get('sentiment', 'neutral')}] {p.get('position_summary', 'N/A')}")
            click.echo(f"    Tags: {p.get('tag_names', 'none')}")
            click.echo(f"    Source: {p.get('source_url', 'N/A')}")

    conn.close()


@cli.command()
@click.option("--office", type=click.Choice(["Senate", "House", "Governor"]), default=None)
@click.option("--state", default=None, help="Filter by state (two-letter code)")
@click.option("--party", default=None, help="Filter by party (DEM, REP, etc.)")
@click.option("--has-url", is_flag=True, help="Only show candidates with campaign URLs")
@click.option("--limit", default=50, help="Max results to show")
def candidates(office, state, party, has_url, limit):
    """List candidates in the database."""
    conn = get_connection()
    query = "SELECT * FROM candidates WHERE 1=1"
    params = []

    if office:
        query += " AND office = ?"
        params.append(office)
    if state:
        query += " AND state = ?"
        params.append(state.upper())
    if party:
        query += " AND party = ?"
        params.append(party.upper())
    if has_url:
        query += " AND campaign_url IS NOT NULL"

    query += " ORDER BY state, name LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    conn.close()

    if not rows:
        click.echo("No candidates found matching filters.")
        return

    click.echo(f"{'Name':<30} {'Party':<6} {'Office':<10} {'State':<7} {'URL':<5} {'Source':<12}")
    click.echo("-" * 75)
    for r in rows:
        has = "Yes" if r["campaign_url"] else "No"
        click.echo(
            f"{r['name']:<30} {r['party']:<6} {r['office']:<10} {r['state']:<7} {has:<5} {r['roster_source']:<12}"
        )
    click.echo(f"\n{len(rows)} candidates shown")


@cli.command()
def stats():
    """Show database statistics."""
    conn = get_connection()

    total = conn.execute("SELECT COUNT(*) as n FROM candidates").fetchone()["n"]
    if total == 0:
        click.echo("Database is empty. Run 'roster' first.")
        conn.close()
        return

    click.echo("=== Candidate Stats ===")

    # By office
    rows = conn.execute(
        "SELECT office, COUNT(*) as n FROM candidates GROUP BY office ORDER BY n DESC"
    ).fetchall()
    for r in rows:
        click.echo(f"  {r['office']}: {r['n']}")

    # By party
    click.echo("\nBy party:")
    rows = conn.execute(
        "SELECT party_full, COUNT(*) as n FROM candidates GROUP BY party_full ORDER BY n DESC LIMIT 10"
    ).fetchall()
    for r in rows:
        click.echo(f"  {r['party_full'] or 'Unknown'}: {r['n']}")

    # URLs
    with_url = conn.execute(
        "SELECT COUNT(*) as n FROM candidates WHERE campaign_url IS NOT NULL"
    ).fetchone()["n"]
    click.echo(f"\nWith campaign URL: {with_url}/{total}")

    # Content
    content_count = conn.execute("SELECT COUNT(*) as n FROM content").fetchone()["n"]
    if content_count:
        ai_relevant = conn.execute(
            "SELECT COUNT(*) as n FROM content WHERE is_ai_relevant = 1"
        ).fetchone()["n"]
        click.echo(f"\n=== Content Stats ===")
        click.echo(f"  Pages scraped: {content_count}")
        click.echo(f"  AI-relevant: {ai_relevant}")

    # Excerpts
    excerpt_count = conn.execute("SELECT COUNT(*) as n FROM excerpts").fetchone()["n"]
    if excerpt_count:
        click.echo(f"\n=== Excerpt Stats ===")
        click.echo(f"  Excerpts: {excerpt_count}")
        rows = conn.execute("""
            SELECT t.name, COUNT(*) as n FROM excerpt_tags et
            JOIN tags t ON et.tag_id = t.id
            GROUP BY t.name ORDER BY n DESC LIMIT 10
        """).fetchall()
        if rows:
            click.echo("  Top tags:")
            for r in rows:
                click.echo(f"    {r['name']}: {r['n']}")

    conn.close()


@cli.command()
@click.option("--format", "fmt", type=click.Choice(["csv", "json"]), default="csv")
@click.option("--output", "-o", type=click.Path(), help="Output file path")
def export(fmt, output):
    """Export candidates data."""
    conn = get_connection()
    rows = conn.execute("SELECT * FROM candidates ORDER BY state, office, name").fetchall()
    conn.close()

    if fmt == "csv":
        out = open(output, "w", newline="") if output else sys.stdout
        writer = csv.writer(out)
        writer.writerow([
            "name", "party", "party_full", "office", "state", "district",
            "incumbent_status", "campaign_url", "fec_candidate_id", "roster_source"
        ])
        for r in rows:
            writer.writerow([
                r["name"], r["party"], r["party_full"], r["office"], r["state"],
                r["district"], r["incumbent_status"], r["campaign_url"],
                r["fec_candidate_id"], r["roster_source"]
            ])
        if output:
            out.close()
            click.echo(f"Exported {len(rows)} candidates to {output}")
    elif fmt == "json":
        import json
        data = [dict(r) for r in rows]
        if output:
            with open(output, "w") as f:
                json.dump(data, f, indent=2, default=str)
            click.echo(f"Exported {len(rows)} candidates to {output}")
        else:
            click.echo(json.dumps(data, indent=2, default=str))


if __name__ == "__main__":
    cli()
