"""
Read-only query functions for the news agent dashboard.
Mirrors the historical_reports.py / batch_runner.py separation
from the Jira-Phrase project.
"""

from news_db import get_db


def get_all_articles(min_score=None, category=None, digested_only=None, source=None, since=None, limit=200):
	conn = get_db()
	query = "SELECT * FROM articles WHERE processed = 1"
	params = []

	if min_score is not None:
		query += " AND importance_score >= ?"
		params.append(min_score)
	if category:
		query += " AND category = ?"
		params.append(category)
	if digested_only is not None:
		query += " AND digested = ?"
		params.append(1 if digested_only else 0)
	if source:
		query += " AND source = ?"
		params.append(source)
	if since:  # NEW
		query += " AND fetched_at >= ?"
		params.append(since)

	query += " ORDER BY fetched_at DESC LIMIT ?"
	params.append(limit)

	rows = conn.execute(query, params).fetchall()
	conn.close()
	return [dict(r) for r in rows]


def get_summary_stats(since=None):
	conn = get_db()
	query = """
		SELECT
			COUNT(*) AS total_ingested,
			SUM(CASE WHEN processed = 1 THEN 1 ELSE 0 END) AS total_scored,
			SUM(CASE WHEN digested = 1 THEN 1 ELSE 0 END) AS total_digested,
			SUM(CASE WHEN used_research = 1 THEN 1 ELSE 0 END) AS total_research_used,
			AVG(CASE WHEN processed = 1 THEN importance_score END) AS avg_score
		FROM articles
	"""
	params = []
	if since:
		query += " WHERE fetched_at >= ?"
		params.append(since)

	row = conn.execute(query, params).fetchone()
	conn.close()

	total_scored = row["total_scored"] or 0
	research_used = row["total_research_used"] or 0

	return {
		"total_ingested": row["total_ingested"] or 0,
		"total_scored": total_scored,
		"total_digested": row["total_digested"] or 0,
		"total_research_used": research_used,
		"research_rate": (research_used / total_scored * 100) if total_scored else 0,
		"avg_score": round(row["avg_score"], 2) if row["avg_score"] else 0,
	}


def get_category_breakdown(since=None):
	conn = get_db()
	query = "SELECT category, COUNT(*) AS count FROM articles WHERE processed = 1 AND category IS NOT NULL"
	params = []
	if since:
		query += " AND fetched_at >= ?"
		params.append(since)
	query += " GROUP BY category ORDER BY count DESC"

	rows = conn.execute(query, params).fetchall()
	conn.close()
	return [dict(r) for r in rows]


def get_score_distribution(since=None):
	conn = get_db()
	query = "SELECT importance_score, COUNT(*) AS count FROM articles WHERE processed = 1 AND importance_score IS NOT NULL"
	params = []
	if since:
		query += " AND fetched_at >= ?"
		params.append(since)
	query += " GROUP BY importance_score ORDER BY importance_score DESC"

	rows = conn.execute(query, params).fetchall()
	conn.close()
	return [dict(r) for r in rows]


def get_research_examples(limit=10):
	"""Articles where Claude chose to use web search — the agentic
	decision-making evidence worth surfacing explicitly."""
	conn = get_db()
	rows = conn.execute(
		"""
		SELECT * FROM articles
		WHERE used_research = 1
		ORDER BY fetched_at DESC
		LIMIT ?
		""",
		(limit,),
	).fetchall()
	conn.close()
	return [dict(r) for r in rows]


def get_available_sources():
	conn = get_db()
	rows = conn.execute("SELECT DISTINCT source FROM articles ORDER BY source").fetchall()
	conn.close()
	return [r["source"] for r in rows]