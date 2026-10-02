import logging
from news_ingest import fetch_and_store_articles
from news_agent import process_pending_articles
from news_digest import send_digest

logging.basicConfig(filename="news_agent.log", level=logging.INFO,
					 format="%(asctime)s %(levelname)s %(message)s")


def run_weekly_pipeline():
	print("\n🗞️ Starting weekly news agent run...")

	try:
		fetch_and_store_articles()
	except Exception as e:
		logging.error(f"Ingestion failed: {e}")
		print(f"❌ Ingestion failed: {e}")

	try:
		process_pending_articles()
	except Exception as e:
		logging.error(f"Scoring failed: {e}")
		print(f"❌ Scoring failed: {e}")

	try:
		send_digest()
	except Exception as e:
		logging.error(f"Digest send failed: {e}")
		print(f"❌ Digest send failed: {e}")

	print("✅ Weekly run complete.\n")


if __name__ == "__main__":
	run_weekly_pipeline()