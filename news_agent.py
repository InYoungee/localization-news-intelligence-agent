import os
import json
import anthropic
from dotenv import load_dotenv
import sys
from news_db import get_unprocessed_articles, update_article_score, mark_processing_failed, requeue_unscored_articles


load_dotenv()
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def extract_text(response):
	"""Finds the FINAL text block in a response — important once tool use
	is involved, since Claude may write preliminary reasoning or call a
	tool before producing its actual final answer. The first text block
	is correct for simple responses too, so this is a safe change either way."""
	text_blocks = [block for block in response.content if block.type == "text"]
	if text_blocks:
		return text_blocks[-1].text.strip()
	raise ValueError(
		f"No text block found. stop_reason={response.stop_reason}, "
		f"block types present: {[b.type for b in response.content]}"
	)


def call_claude_with_retry(prompt, max_retries=3):
	"""Retries on transient overload (529) with exponential backoff."""
	import time
	for attempt in range(1, max_retries + 1):
		try:
			response = client.messages.create(
				model="claude-sonnet-5",
				max_tokens=700,  # CHANGED from 400 — was truncating longer summaries mid-JSON
				thinking={"type": "disabled"},
				messages=[{"role": "user", "content": prompt}],
			)
			if response.stop_reason == "max_tokens":
				print(f"⚠️ Response hit max_tokens limit — may be truncated JSON")
			return extract_text(response)
		except Exception as e:
			is_overloaded = "overloaded" in str(e).lower() or "529" in str(e)
			if is_overloaded and attempt < max_retries:
				wait = 2 ** attempt
				print(f"⚠️ Claude API overloaded (attempt {attempt}/{max_retries}) — retrying in {wait}s...")
				time.sleep(wait)
			else:
				raise


def score_article(source, title, excerpt):
	prompt = f"""You are a news filter for a Localization Project Manager who works in
game localization, tracks AI/MT industry trends, and manages TMS/vendor relationships.

Source: {source}
Title: {title}
Excerpt: {excerpt[:800]}

If the excerpt alone is too thin to judge this article's significance (e.g. a funding round,
acquisition, or product launch with no real detail), you may use web search to find one or
two more facts before scoring — but only when genuinely necessary, not for every article.
Most articles have enough context in the excerpt alone.

Score using these concrete anchors:

5 = Directly about localization/translation industry (TMS tools, LSP news, localization-specific
    AI/MT developments) OR a major foundational AI model release/capability shift that would
    change how translation or content workflows are done.
4 = Significant AI industry news with clear implications for translation/localization work
    (a new LLM capability relevant to MT, a major vendor tool announcement, AI agent
    developments relevant to workflow automation).
3 = Broader AI/tech industry news worth knowing to stay current in the field, even without a
    direct localization angle (funding, model releases, industry shifts).
2 = Tangentially related — mentions AI or gaming industry but not clearly useful for this
    specific role.
1 = Not relevant to localization, AI/MT, or game industry work at all.

Categorize using exactly one of these labels:
- "AI/MT" — AI/LLM model releases, machine translation technology, AI capability shifts
- "Localization" — localization industry business news, LSP/market news, loc-specific trends
- "TMS/Vendor" — specific tool/platform announcements (Phrase, Smartling, DeepL, etc.)
- "i18n" — internationalization engineering: Unicode, RTL support, pseudo-localization,
  string externalization, build/engineering practices for multilingual software
- "QA" — linguistic quality assurance, localization testing, review processes, quality frameworks
- "Gaming Industry" — game industry business news without a clear localization/AI angle
- "General Tech" — broader tech news with no localization or direct AI/MT relevance
- "Not Relevant" — none of the above apply

Respond with ONLY a JSON object, no other text, in this exact shape:
{{
  "importance_score": <integer 1-5, using the anchors above>,
  "category": "<one of: AI/MT, Localization, TMS/Vendor, i18n, QA, Gaming Industry, General Tech, Not Relevant>",
  "summary": "<ONE concise sentence, max ~25 words, summarizing what the article is about>",
  "used_research": <true if you searched the web for additional context, false otherwise>
}}"""

	response = client.messages.create(
		model="claude-sonnet-5",
		max_tokens=700,
		thinking={"type": "disabled"},
		tools=[{"type": "web_search_20250305", "name": "web_search"}],  # NEW — real agentic capability
		messages=[{"role": "user", "content": prompt}],
	)

	raw = extract_text(response)
	cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()

	try:
		return json.loads(cleaned)
	except json.JSONDecodeError:
		print(f"⚠️ Could not parse Claude's response as JSON for '{title[:60]}...': {raw[:200]}")
		return None


def process_pending_articles():
	total_scored = 0
	while True:
		articles = get_unprocessed_articles(limit=50)
		if not articles:
			break

		print(f"Scoring {len(articles)} article(s)...")
		for article in articles:
			result = score_article(article["source"], article["title"], article["excerpt"])

			if result is None:
				mark_processing_failed(article["link"])
				continue

			update_article_score(
				link=article["link"],
				importance_score=result.get("importance_score"),
				category=result.get("category"),
				summary=result.get("summary"),
				used_research=result.get("used_research", False),
			)
			print(f"  [{result.get('importance_score')}/5] {article['source']}: {article['title'][:70]}")
			total_scored += 1

	print(f"\nTotal scored this run: {total_scored}")
	return total_scored


if __name__ == "__main__":
	if "--requeue-failed" in sys.argv:
		requeue_unscored_articles()

	process_pending_articles()