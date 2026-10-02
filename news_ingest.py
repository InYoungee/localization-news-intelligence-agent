import feedparser
import requests
from news_sources import NEWS_SOURCES, FEED_HEADERS
from news_db import initialize_db, insert_article
from datetime import datetime, timedelta, timezone
import calendar

MAX_ARTICLE_AGE_DAYS = 7  # only ingest articles from the last week


def is_recent_enough(entry):
    """Uses feedparser's normalized published_parsed (a UTC struct_time)
    rather than raw date strings, which vary wildly in format across feeds."""
    parsed = entry.get("published_parsed")
    if not parsed:
        return True  # no date info — keep it rather than silently drop; can't judge age
    published_dt = datetime.fromtimestamp(calendar.timegm(parsed), tz=timezone.utc)
    cutoff = datetime.now(timezone.utc) - timedelta(days=MAX_ARTICLE_AGE_DAYS)
    return published_dt >= cutoff

def fetch_and_store_articles():
    initialize_db()
    total_new = 0
    total_skipped_old = 0

    for source_name, feed_url in NEWS_SOURCES.items():
        try:
            response = requests.get(feed_url, headers=FEED_HEADERS, timeout=15)
            response.raise_for_status()
            feed = feedparser.parse(response.content)

            new_count = 0
            skipped_count = 0
            for entry in feed.entries:
                if not is_recent_enough(entry):
                    skipped_count += 1
                    continue

                link = entry.get("link")
                title = entry.get("title", "")
                excerpt = entry.get("summary", "") or entry.get("description", "")
                published_at = entry.get("published", "")

                if link and title:
                    insert_article(link, source_name, title, excerpt, published_at)
                    new_count += 1

            print(f"✅ {source_name}: {new_count} recent, {skipped_count} older than {MAX_ARTICLE_AGE_DAYS}d skipped")
            total_new += new_count
            total_skipped_old += skipped_count

        except Exception as e:
            print(f"⚠️ {source_name}: failed to fetch — {e}")

    print(f"\nDone. {total_new} recent entries stored, {total_skipped_old} older entries skipped.")


if __name__ == "__main__":
    fetch_and_store_articles()