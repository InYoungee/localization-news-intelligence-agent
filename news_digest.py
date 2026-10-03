import os
import requests
from collections import defaultdict
from dotenv import load_dotenv

from news_db import get_articles_for_digest, mark_as_digested

load_dotenv()
SLACK_WEBHOOK_URL = os.getenv("NEWS_SLACK_WEBHOOK_URL")

MIN_SCORE_FOR_DIGEST = 3  # adjustable


def group_by_category(articles):
    grouped = defaultdict(list)
    for article in articles:
        grouped[article["category"] or "Uncategorized"].append(article)
    return grouped


def build_slack_blocks(grouped_articles):
    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": "📰 Localization & AI Industry Digest"}},
    ]

    for category, articles in grouped_articles.items():
        blocks.append({"type": "divider"})
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"*{category}*"}})

        for article in articles:
            stars = "⭐" * article["importance_score"]
            text = (
                f"{stars} <{article['link']}|{article['title']}>\n"
                f"_{article['source']}_ — {article['summary']}"
            )
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": text}})

    return blocks


def send_digest():
    if not SLACK_WEBHOOK_URL:
        print("⚠️ NEWS_SLACK_WEBHOOK_URL not set — skipping digest send.")
        return

    articles = get_articles_for_digest(min_score=MIN_SCORE_FOR_DIGEST)

    if not articles:
        print(f"No articles scoring {MIN_SCORE_FOR_DIGEST}+ ready to digest.")
        return

    grouped = group_by_category(articles)
    blocks = build_slack_blocks(grouped)

    # Slack caps messages at 50 blocks — trim with a note rather than fail silently
    if len(blocks) > 50:
        blocks = blocks[:49]
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": "_...digest truncated, too many articles for one message_"}})

    response = requests.post(SLACK_WEBHOOK_URL, json={"blocks": blocks}, timeout=15)

    if response.status_code == 200:
        print(f"✅ Digest sent: {len(articles)} articles across {len(grouped)} categories.")
        mark_as_digested([a["link"] for a in articles])
    else:
        print(f"⚠️ Digest send failed ({response.status_code}): {response.text}")


if __name__ == "__main__":
    send_digest()