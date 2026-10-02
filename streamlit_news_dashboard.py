"""
Localization & AI News Agent — Archive Dashboard
Reads from news_agent.db via news_reports.py.

Run with: streamlit run streamlit_news_dashboard.py
"""

from datetime import datetime, timedelta, timezone

import streamlit as st
import pandas as pd
import plotly.express as px

import news_reports as nr

st.set_page_config(
    page_title="News Agent Dashboard",
    page_icon="📰",
    layout="wide",
)

st.markdown("""
<style>
    .block-container {
        max-width: 95% !important;
        padding-left: 2rem !important;
        padding-right: 2rem !important;
        padding-top: 2rem !important;
    }
    [data-testid="stMetricValue"] { font-size: 2.5rem !important; }
    [data-testid="stMetricLabel"] { font-size: 1.2rem !important; }
    .stMarkdown, .stCaption, p, li { font-size: 1.15rem !important; }
    div[data-testid="stDataFrame"] * { font-size: 1.1rem !important; }
    div[data-testid="stSelectbox"] label, div[data-testid="stSelectbox"] div { font-size: 1.1rem !important; }
    h1 { font-size: 2.6rem !important; }
    h2 { font-size: 1.8rem !important; }
    h3 { font-size: 1.4rem !important; }
</style>
""", unsafe_allow_html=True)


def apply_large_fonts(fig):
    """Plotly renders its own text as SVG, outside the page's CSS —
    font sizes have to be set through Plotly's layout config directly,
    the CSS block above has no effect on chart legends/axes/labels."""
    fig.update_layout(
        font=dict(size=16),
        legend=dict(font=dict(size=15)),
        title_font=dict(size=20),
    )
    fig.update_xaxes(title_font=dict(size=16), tickfont=dict(size=14))
    fig.update_yaxes(title_font=dict(size=16), tickfont=dict(size=14))
    return fig


st.title("📰 Localization & AI News Agent")
st.caption("Autonomous RSS ingestion → Claude relevance scoring (with agentic web search) → weekly Slack digest")

# ============================================================
# Date range control — applies globally to Overview + Archive
# ============================================================

range_cols = st.columns([2, 2, 4])
with range_cols[0]:
    range_choice = st.selectbox(
        "Time range",
        options=["Last 7 Days", "Last 30 Days", "Last 90 Days", "Specific Month", "All Time"],
        index=1,
    )

since_filter = None
if range_choice == "Last 7 Days":
    since_filter = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
elif range_choice == "Last 30 Days":
    since_filter = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
elif range_choice == "Last 90 Days":
    since_filter = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
elif range_choice == "Specific Month":
    with range_cols[1]:
        month_picked = st.date_input("Pick any date in the month", value=datetime.now())
    month_start = datetime(month_picked.year, month_picked.month, 1, tzinfo=timezone.utc)
    since_filter = month_start.isoformat()
    # NOTE: this only sets a lower bound (from the start of that month onward) —
    # it does not cap the upper end, so "Specific Month" currently shows
    # "everything since that month began," not an isolated single-month window.
# "All Time" leaves since_filter as None — no filtering applied

if st.button("🔄 Refresh data"):
    st.cache_data.clear()

overview_tab, archive_tab, research_tab = st.tabs(["📊 Overview", "🗂️ Full Archive", "🔍 Agentic Research"])


# ============================================================
# Cached data loaders
# ============================================================

@st.cache_data(ttl=30)
def load_summary(since):
    return nr.get_summary_stats(since=since)

@st.cache_data(ttl=30)
def load_categories(since):
    return nr.get_category_breakdown(since=since)

@st.cache_data(ttl=30)
def load_score_distribution(since):
    return nr.get_score_distribution(since=since)

@st.cache_data(ttl=30)
def load_articles(min_score=None, category=None, digested_only=None, source=None, since=None, limit=500):
    return nr.get_all_articles(min_score=min_score, category=category,
                                digested_only=digested_only, source=source,
                                since=since, limit=limit)

@st.cache_data(ttl=30)
def load_research_examples(limit=50):
    return nr.get_research_examples(limit=limit)

@st.cache_data(ttl=30)
def load_sources():
    return nr.get_available_sources()


# ============================================================
# OVERVIEW TAB
# ============================================================

with overview_tab:
    summary = load_summary(since_filter)

    st.subheader("Key Metrics")
    kpi_cols = st.columns(5)
    kpi_cols[0].metric("Articles Ingested", summary["total_ingested"])
    kpi_cols[1].metric("Scored", summary["total_scored"])
    kpi_cols[2].metric("Sent to Slack", summary["total_digested"])
    kpi_cols[3].metric("Avg. Importance", f"{summary['avg_score']:.2f} / 5")
    kpi_cols[4].metric("🔍 Used Web Research", f"{summary['total_research_used']} ({summary['research_rate']:.1f}%)")

    st.caption("\"Used Web Research\" counts articles where Claude independently decided the RSS excerpt "
               "wasn't enough context and chose to search the web before scoring — a real agentic decision, "
               "not a fixed step in the pipeline.")

    st.divider()
    left_col, right_col = st.columns(2)

    with left_col:
        st.subheader("Score Distribution")
        scores = load_score_distribution(since_filter)
        if not scores:
            st.info("No scored articles in this time range.")
        else:
            score_df = pd.DataFrame(scores)
            fig = px.bar(score_df, x="importance_score", y="count",
                         labels={"importance_score": "Importance Score", "count": "Articles"})
            fig.update_xaxes(dtick=1)
            fig = apply_large_fonts(fig)
            fig.update_layout(margin=dict(t=10, b=10, l=10, r=10))
            st.plotly_chart(fig, use_container_width=True)

    with right_col:
        st.subheader("Category Breakdown")
        categories = load_categories(since_filter)
        if not categories:
            st.info("No category data in this time range.")
        else:
            cat_df = pd.DataFrame(categories)
            fig = px.pie(cat_df, names="category", values="count", hole=0.4)
            fig = apply_large_fonts(fig)
            fig.update_layout(margin=dict(t=10, b=10, l=10, r=10))
            st.plotly_chart(fig, use_container_width=True)


# ============================================================
# FULL ARCHIVE TAB
# ============================================================

with archive_tab:
    st.subheader("Full Article Archive")

    filter_cols = st.columns(4)
    with filter_cols[0]:
        min_score = st.selectbox("Min importance score", options=[None, 1, 2, 3, 4, 5], index=0)
    with filter_cols[1]:
        categories = ["All"] + [c["category"] for c in load_categories(since_filter)]
        category_selected = st.selectbox("Category", options=categories)
        category_filter = None if category_selected == "All" else category_selected
    with filter_cols[2]:
        sources = ["All"] + load_sources()
        source_selected = st.selectbox("Source", options=sources)
        source_filter = None if source_selected == "All" else source_selected
    with filter_cols[3]:
        digest_options = {"All": None, "Sent to Slack": True, "Not yet sent": False}
        digest_selected = st.selectbox("Digest status", options=list(digest_options.keys()))
        digested_filter = digest_options[digest_selected]

    articles = load_articles(min_score=min_score, category=category_filter,
                              digested_only=digested_filter, source=source_filter,
                              since=since_filter, limit=500)

    if not articles:
        st.warning("No articles match these filters.")
    else:
        df = pd.DataFrame(articles)
        df["🔍"] = df["used_research"].apply(lambda x: "🔍" if x else "")
        df["digested"] = df["digested"].apply(lambda x: "✅" if x else "—")

        display_df = df[["🔍", "source", "title", "category", "importance_score", "summary", "digested", "fetched_at"]]
        display_df = display_df.rename(columns={"importance_score": "score", "fetched_at": "fetched"})

        st.dataframe(display_df, use_container_width=True, hide_index=True)
        st.caption(f"Showing {len(articles)} article(s).")


# ============================================================
# AGENTIC RESEARCH TAB
# ============================================================

with research_tab:
    st.subheader("Articles Where the Agent Chose to Research")
    st.caption("Claude was given a web_search tool and explicit discretion to use it only when an article's "
               "RSS excerpt was too thin to judge significance. These are the cases where it decided to act.")

    research_articles = load_research_examples(limit=50)

    if not research_articles:
        st.info("No articles have triggered web research yet. This is expected if excerpts have been "
                "detailed enough on their own — the agent is designed to search selectively, not by default.")
    else:
        for article in research_articles:
            with st.container(border=True):
                st.markdown(f"**[{article['title']}]({article['link']})**")
                st.caption(f"{article['source']} · {article['category']} · Score: {article['importance_score']}/5")
                st.write(article["summary"])