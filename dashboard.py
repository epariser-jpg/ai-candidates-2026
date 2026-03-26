"""Interactive dashboard for 2026 Candidates AI Positions Database."""

import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

DB_PATH = Path(__file__).parent / "data" / "candidates_ai.db"

st.set_page_config(
    page_title="2026 Candidates on AI",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .block-container { padding-top: 1.5rem; }
    h1 { font-size: 1.8rem !important; }
    h2 { font-size: 1.3rem !important; }
</style>
""", unsafe_allow_html=True)


PLOTLY_CONFIG = {"displayModeBar": False}


def get_conn():
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def query_df(sql, params=None):
    return pd.read_sql_query(sql, get_conn(), params=params or [])


def fmt_tag(tag):
    return tag.replace("ai_", "").replace("tech_", "").replace("_", " ").title()


SENTIMENT_COLORS = {
    "supportive": "#27ae60", "cautious": "#f39c12",
    "opposed": "#e74c3c", "neutral": "#95a5a6", "mixed": "#8e44ad"
}
SENTIMENT_ICONS = {
    "supportive": "🟢", "cautious": "🟡",
    "opposed": "🔴", "neutral": "⚪", "mixed": "🟣"
}
PARTY_COLORS = {
    "DEM": "#2171b5", "REP": "#cb181d", "IND": "#41ab5d",
    "LIB": "#fee391", "GRE": "#238b45",
    "Democrat": "#2171b5", "Republican": "#cb181d"
}

PAGES = [
    "📊 Overview",
    "📝 Analysis",
    "🏛️ By Party",
    "🏷️ By Topic",
    "👤 By Candidate",
    "🗺️ By State",
    "🔍 Search",
    "💡 Feedback",
]

GITHUB_REPO = "epariser-jpg/ai-candidates-2026"


# ── Navigation helpers ────────────────────────────────────────────
def navigate(page, **kwargs):
    """Set session state to navigate to a page with context."""
    st.session_state["_nav_target"] = page
    for k, v in kwargs.items():
        st.session_state[f"nav_{k}"] = v


def get_nav(key, default=None):
    """Get a navigation parameter, then clear it."""
    val = st.session_state.pop(f"nav_{key}", default)
    return val


# ── Candidate summary builder ────────────────────────────────────
def build_candidate_summary(candidate, excerpts_df):
    """Build a narrative summary paragraph from a candidate's excerpts."""
    name = candidate["name"]
    party_label = {"DEM": "Democratic", "REP": "Republican", "IND": "Independent",
                   "LIB": "Libertarian", "GRE": "Green"}.get(candidate["party"], candidate["party"])

    # Gather key data
    sentiments = excerpts_df["sentiment"].value_counts()
    total = len(excerpts_df)

    # Collect unique tags
    all_tags = []
    for tags_str in excerpts_df["tags"].dropna():
        all_tags.extend([t.strip() for t in tags_str.split(",")])
    top_tags = [fmt_tag(t) for t, _ in pd.Series(all_tags).value_counts().head(4).items()]

    # Get high-confidence position summaries (deduplicated)
    high_conf = excerpts_df[excerpts_df["confidence"] >= 0.75].sort_values("confidence", ascending=False)
    positions = []
    seen = set()
    for _, row in high_conf.iterrows():
        summary = row.get("position_summary", "")
        if summary and summary not in seen:
            seen.add(summary)
            positions.append(summary)
        if len(positions) >= 4:
            break

    # Build the paragraph
    # Opening: overall stance
    dominant = sentiments.index[0] if len(sentiments) > 0 else "neutral"
    stance_map = {
        "supportive": "generally embraces AI and technology",
        "cautious": "takes a cautious approach to AI, emphasizing the need for guardrails",
        "opposed": "takes a critical stance toward AI and automated systems",
        "neutral": "addresses AI-related topics",
        "mixed": "has a mixed position on AI, supporting some applications while opposing others",
    }
    stance = stance_map.get(dominant, "addresses AI-related topics")

    # Topics
    if top_tags:
        topics_str = ", ".join(top_tags[:-1]) + f", and {top_tags[-1]}" if len(top_tags) > 1 else top_tags[0]
    else:
        topics_str = "AI-related issues"

    parts = [f"**{name}** ({party_label}) {stance}, with **{total} AI-related positions** "
             f"on their campaign website touching on {topics_str}."]

    # Key positions
    if positions:
        parts.append(" ".join(positions[:3]))

    # Sentiment mix if not one-sided
    if len(sentiments) > 1:
        sent_parts = []
        for s, count in sentiments.items():
            pct = count * 100 // total
            if pct >= 15:
                sent_parts.append(f"{s} ({pct}%)")
        if sent_parts:
            parts.append(f"Overall tone: {', '.join(sent_parts)}.")

    return " ".join(parts)


# ── Reusable excerpt renderer ────────────────────────────────────
def render_excerpts(df, show_candidate=True):
    """Render a list of excerpts as expanders."""
    if df.empty:
        st.info("No excerpts match these filters.")
        return

    for _, row in df.iterrows():
        icon = SENTIMENT_ICONS.get(row.get("sentiment", ""), "⚪")
        star = "⭐ " if row.get("candidate_tier") == "leading" else ""
        if show_candidate:
            state_str = f", {row['state']}" if "state" in row.index else ""
            label = f"{icon} {star}{row['name']} ({row['party']}{state_str}) — {row['sentiment']} ({row.get('confidence', 0):.0%})"
        else:
            label = f"{icon} {(row.get('position_summary') or 'No summary')[:100]}"

        with st.expander(label):
            if row.get("position_summary"):
                st.markdown(f"**{row['position_summary']}**")
            if row.get("excerpt_text"):
                st.markdown(f"> *\"{row['excerpt_text']}\"*")
            if row.get("tags"):
                st.markdown(f"**Topics:** {', '.join(fmt_tag(t.strip()) for t in str(row['tags']).split(','))}")
            source = row.get("source_url", "")
            if source:
                st.caption(f"Confidence: {row.get('confidence', 0):.0%}  ·  [Source →]({source})")


# ── Sidebar ──────────────────────────────────────────────────────
st.sidebar.title("🏛️ 2026 Candidates on AI")
st.sidebar.caption("How are Senate candidates talking about artificial intelligence?")
st.sidebar.divider()

# If a click-through navigation was triggered, apply it before rendering the radio
if "_nav_target" in st.session_state:
    _target = st.session_state.pop("_nav_target")
    if _target in PAGES:
        st.session_state["page_radio"] = _target

page = st.sidebar.radio("", PAGES, key="page_radio")

st.sidebar.divider()
if st.sidebar.button("💡 Share your ideas to improve this site", use_container_width=True):
    navigate("💡 Feedback")
    st.rerun()
st.sidebar.caption("Data: Campaign websites scraped Mar 2026.\nAI positions extracted via Claude Sonnet.")


# ═══════════════════════════════════════════════════════════════════
# OVERVIEW
# ═══════════════════════════════════════════════════════════════════
if page == "📊 Overview":
    st.title("2026 Senate Candidates & AI")
    st.caption("What are candidates saying about artificial intelligence on their campaign websites?")

    stats = query_df("""
        SELECT
            (SELECT COUNT(DISTINCT candidate_id) FROM content) as candidates_scraped,
            (SELECT COUNT(*) FROM content) as pages_scraped,
            (SELECT COUNT(*) FROM content WHERE is_ai_relevant = 1) as ai_relevant_pages,
            (SELECT COUNT(*) FROM excerpts) as total_excerpts,
            (SELECT COUNT(DISTINCT candidate_id) FROM excerpts) as candidates_with_positions,
            (SELECT COUNT(*) FROM candidates WHERE candidate_tier = 'leading') as total_leading,
            (SELECT COUNT(DISTINCT e.candidate_id) FROM excerpts e
             JOIN candidates c ON e.candidate_id = c.id WHERE c.candidate_tier = 'leading') as leading_with_positions
    """).iloc[0]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Campaign Sites Scraped", int(stats["candidates_scraped"]))
    c2.metric("Pages Analyzed", f"{int(stats['pages_scraped']):,}")
    c3.metric("Candidates Mentioning AI", int(stats["candidates_with_positions"]))
    c4.metric("Leading Candidates w/ AI",
              f"{int(stats['leading_with_positions'])} of {int(stats['total_leading'])}")

    st.divider()
    col1, col2 = st.columns(2)

    # ── Top tags (clickable) ──
    with col1:
        st.subheader("Most Discussed AI Topics")
        st.caption("Click a bar to explore that topic")
        tags_df = query_df("""
            SELECT t.name as tag, COUNT(*) as count
            FROM excerpt_tags et JOIN tags t ON et.tag_id = t.id
            GROUP BY t.name ORDER BY count DESC LIMIT 12
        """)
        if not tags_df.empty:
            tags_df["label"] = tags_df["tag"].apply(fmt_tag)
            fig = px.bar(tags_df, x="count", y="label", orientation="h",
                         color="count", color_continuous_scale="Blues",
                         custom_data=["tag"])
            fig.update_layout(yaxis=dict(autorange="reversed"), showlegend=False,
                              coloraxis_showscale=False, height=400,
                              margin=dict(l=0, r=20, t=10, b=20))
            fig.update_xaxes(title="Mentions across all candidates")
            fig.update_yaxes(title="")
            event = st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG, on_select="rerun", key="overview_tags")
            if event and event.selection and event.selection.points:
                clicked_tag = event.selection.points[0]["customdata"][0]
                navigate("🏷️ By Topic", tag=clicked_tag)
                st.rerun()

    # ── Sentiment donut (clickable) ──
    with col2:
        st.subheader("Sentiment Toward AI Topics")
        st.caption("Click a slice to see all excerpts with that sentiment")
        sent_df = query_df("""
            SELECT sentiment, COUNT(*) as count FROM excerpts
            WHERE sentiment IS NOT NULL GROUP BY sentiment ORDER BY count DESC
        """)
        if not sent_df.empty:
            fig = px.pie(sent_df, values="count", names="sentiment",
                         color="sentiment", color_discrete_map=SENTIMENT_COLORS, hole=0.45)
            fig.update_traces(textposition="outside", textinfo="label+percent")
            fig.update_layout(height=400, margin=dict(l=0, r=0, t=10, b=20), showlegend=False)
            event = st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG, on_select="rerun", key="overview_sent")
            if event and event.selection and event.selection.points:
                clicked_sent = event.selection.points[0]["label"]
                navigate("🔍 Search", sentiment=clicked_sent)
                st.rerun()

    st.divider()
    col1, col2 = st.columns(2)

    # ── Top candidates (clickable) ──
    with col1:
        st.subheader("Most AI-Engaged Candidates")
        st.caption("Click a bar to see that candidate's positions")
        top_df = query_df("""
            SELECT ca.id, ca.name, ca.party, ca.state, ca.candidate_tier, COUNT(e.id) as excerpts
            FROM excerpts e JOIN candidates ca ON e.candidate_id = ca.id
            GROUP BY ca.id ORDER BY excerpts DESC LIMIT 15
        """)
        if not top_df.empty:
            top_df["label"] = top_df.apply(
                lambda r: f"{'⭐ ' if r.get('candidate_tier') == 'leading' else ''}{r['name']} ({r['party']}, {r['state']})",
                axis=1)
            fig = px.bar(top_df, x="excerpts", y="label", orientation="h",
                         color="party", color_discrete_map=PARTY_COLORS,
                         custom_data=["id", "name"])
            fig.update_layout(yaxis=dict(autorange="reversed"), height=450,
                              margin=dict(l=0, r=20, t=10, b=20), legend_title="Party")
            fig.update_xaxes(title="AI-related excerpts")
            fig.update_yaxes(title="")
            event = st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG, on_select="rerun", key="overview_cands")
            if event and event.selection and event.selection.points:
                clicked_id = int(event.selection.points[0]["customdata"][0])
                navigate("👤 By Candidate", candidate_id=clicked_id)
                st.rerun()

    # ── State map (clickable) ──
    with col2:
        st.subheader("AI Mentions by State")
        st.caption("Click a state to explore that race")
        state_df = query_df("""
            SELECT ca.state, COUNT(DISTINCT ca.id) as candidates, COUNT(e.id) as excerpts
            FROM excerpts e JOIN candidates ca ON e.candidate_id = ca.id
            GROUP BY ca.state ORDER BY excerpts DESC
        """)
        if not state_df.empty:
            fig = px.choropleth(state_df, locations="state", locationmode="USA-states",
                                color="excerpts", scope="usa",
                                color_continuous_scale="YlOrRd",
                                custom_data=["state"],
                                labels={"excerpts": "Excerpts", "state": "State"})
            fig.update_layout(height=450, margin=dict(l=0, r=0, t=10, b=0),
                              geo=dict(bgcolor="rgba(0,0,0,0)", lakecolor="rgba(0,0,0,0)"),
                              coloraxis_colorbar=dict(title="Excerpts"))
            event = st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG, on_select="rerun", key="overview_map")
            if event and event.selection and event.selection.points:
                clicked_state = event.selection.points[0].get("location") or event.selection.points[0].get("customdata", [None])[0]
                if clicked_state:
                    navigate("🗺️ By State", state=clicked_state)
                    st.rerun()

    st.divider()
    st.subheader("Key Findings")
    pct_leading = int(stats["leading_with_positions"]) * 100 // max(int(stats["total_leading"]), 1)
    col1, col2, col3 = st.columns(3)
    col1.info(f"**{pct_leading}% of leading candidates** mention AI or AI-adjacent topics on their campaign websites.")
    col2.info(f"**Tech regulation** is the most discussed AI topic, followed by surveillance/privacy and jobs/workforce.")
    col3.info(f"**Democrats engage more** with AI topics. Republicans who do tend to focus on surveillance and opposing regulation.")


# ═══════════════════════════════════════════════════════════════════
# ANALYSIS REPORT
# ═══════════════════════════════════════════════════════════════════
elif page == "📝 Analysis":
    st.title("How 2026 Senate Candidates Are Talking About AI")
    st.caption("An analysis of AI-related positions on campaign websites  ·  March 2026")

    st.markdown("""
---

### The Big Picture

Artificial intelligence has arrived in the 2026 Senate races — but unevenly.
After scraping and analyzing the campaign websites of **77 leading candidates**
across all 33 Senate races, we found that **roughly half (39) mention AI or
AI-adjacent topics** on their campaign sites. That means half of the people who
may shape America's AI policy in the next Congress haven't yet told voters what
they think about it.

Among those who do engage, **416 distinct AI-related positions** emerged, spanning
topics from workforce automation to deepfakes to semiconductor competition with
China. But the nature of that engagement differs starkly between the parties — not
just in what they say, but in *whether they say anything at all*.

---

### The Partisan Divide: Different Conversations, Not Just Different Answers

The most important finding isn't that Democrats and Republicans disagree about AI —
it's that **they're having fundamentally different conversations**.

**Democrats are far more likely to engage.** Among leading candidates, Democrats
produced 103 AI-related excerpts across 24 candidates, compared to just 34
excerpts from 14 Republicans. Most leading Republican candidates simply
don't address AI on their campaign websites.

**Democrats lead with jobs and worker protection.** The single biggest topic in the
Democratic AI conversation is *ai_jobs_workforce* (33 mentions among leading
candidates) — a topic that **no leading Republican candidate addresses**. Democrats
frame AI through the lens of labor. Abdul El-Sayed (D-MI)
[writes](https://abdulforsenate.com/priority/an-economy-for-working-people/):

> *"World-changing technology — like AI — should be in the hands of the people
> rather than unaccountable corporations. Rather than replace us, AI should be
> a tool to enhance our lives."*

James Talarico (D-TX) echoes this on his
[labor platform](https://jamestalarico.com/issue/labor-business/):

> *"Ensure AI works for working people: Protect workers from invasive AI
> surveillance in the workplace; use AI to make jobs safer and less repetitive,
> rather than to eliminate them."*

This framing connects AI to a long-standing
Democratic priority — worker and union power — and reflects real anxiety about
automation's impact on middle-class jobs.

**Republicans lead with competition and strength.** When Republicans do engage with
AI, their top topic is *ai_competitiveness_china* (12 mentions) — framing AI as a
national security and economic competition issue. Mike Rogers (R-MI)
[applauds](https://rogersforsenate.com/news/rogers-applauds-white-house-ai-framework-that-establishes-global-leadership-and-protects-kids-online)
the White House AI framework, emphasizing that it *"establishes global leadership
and protects kids online."* He also
[highlights](https://rogersforsenate.com/news) AI's benefits in *"healthcare,
manufacturing, and agriculture"* while stressing America's need to lead globally.
The Republican AI conversation is more about *winning the AI race* than
*governing AI's consequences*.

**Surveillance is a rare point of agreement — from opposite directions.** Both
parties express concern about AI-powered surveillance, but for different reasons.
Jeff Merkley (D-OR)
[supports](https://www.jeffmerkley.com/2026/02/28/heres-what-i-did-month/)
banning facial recognition and biometric surveillance in immigration enforcement.
Republicans' surveillance concerns tend to be rooted in libertarian
skepticism of government data collection. The policy prescriptions differ, but the
underlying wariness of automated surveillance is bipartisan.

---

### The Boldest Candidates

A handful of candidates have staked out unusually detailed or ambitious AI positions:

**James Talarico (D-TX)** is the most AI-engaged candidate in the dataset by a wide
margin, with 22 excerpts spanning nearly every AI topic. He has
[authored legislation](https://jamestalarico.com/issue/social-media-artificial-intelligence-tech/)
on deepfakes, AI-generated political ads, algorithmic audits, and semiconductor
export controls. He argues that AI requires the same comprehensive regulatory
attention as climate or healthcare, including mandating that
[data centers bear the costs](https://jamestalarico.com/issue/energy-environment/)
of their energy infrastructure rather than passing them to consumers.

**Charles Booker (D-KY)** has the most *radical* AI platform. In his
[Workers' Power and Bill of Rights](https://charlesbooker.org/wpbr/), he proposes:

> *"The centerpiece of my plan is to call for a new federal enforcement agency:
> The Human Labor Protection Bureau... tasked with affirmatively protecting
> workers from harmful displacement and disruption caused by artificial
> intelligence."*

He also calls for banning AI-only hiring/firing decisions, taxing companies that
automate away jobs, a moratorium on data center construction, and establishing
[public ownership stakes](https://charlesbooker.org/wpbr/) in AI development so
*"profits generated from human labor, creativity, and public investment are shared
broadly through a dividend for working people."* He separately proposes
[banning AI tools like GROK](https://charlesbooker.org/stop-the-musk-plan/) that
generate non-consensual images.

**Ed Markey (D-MA)** brings legislative credentials — he's
[co-authored the AI Civil Rights Act](https://www.edmarkey.com/boston-globe-ayanna-pressley-endorses-ed-markey-for-reelection/)
with Pressley. His framing is explicitly
[pro-labor](https://www.edmarkey.com/markey-has-our-back-statewide-machinists-union-endorse-senator-ed-markey-for-re-election/):

> *"At a moment when Big Tech barons are chasing automation without accountability
> and see AI as a way to cut labor costs and crush collective bargaining, I see a
> different future where technology works for workers — not against them."*

**Mark Warner (D-VA)** is notable as one of the few incumbents with a developed AI
position,
[warning](https://www.markwarnerva.com/plan/):

> *"Washington is largely unprepared for the coming AI jobs crisis and we
> urgently need forward-looking policies to prepare our economy for this new era.
> Mark believes the AI companies and big corporations that stand to massively profit
> from this disruption must do their part."*

**Mike Rogers (R-MI)** is the Republican with the most multi-dimensional AI platform,
[supporting](https://rogersforsenate.com/news/rogers-applauds-white-house-ai-framework-that-establishes-global-leadership-and-protects-kids-online)
the White House AI framework while emphasizing child safety and competition with
China. He's a rare Republican who frames AI positively across multiple sectors.

---

### What's Missing

Several gaps in the data are as revealing as what's present:

**Most incumbents are silent.** Major figures like **John Cornyn (TX)**,
**Lindsey Graham (SC)**, **Cory Booker (NJ)**, **John Hickenlooper (CO)**, and
**Susan Collins (ME)** have little to no AI content on their campaign websites,
despite having voted on AI-related legislation. Their Senate office sites (.gov)
may address these issues, but their *campaign* messaging doesn't prioritize AI.

**No leading Republican talks about AI and jobs.** The topic of *ai_jobs_workforce*
— the single biggest AI theme in the dataset — is entirely absent from leading
Republican campaign sites. This is a striking gap given that automation anxiety
cuts across partisan lines in polling. Whether this reflects a strategic choice,
an ideological blind spot, or simply a lag in campaign messaging is unclear, but it
means the parties aren't even debating the same questions.

**Deepfakes and misinformation are almost exclusively Democratic concerns.**
Talarico has
[authored legislation](https://jamestalarico.com/issue/social-media-artificial-intelligence-tech/)
to combat deepfakes and regulate AI-generated political ads. But among leading
Republicans, the topic is virtually absent. Given that AI-generated
disinformation is a bipartisan problem, this silence is notable.

**Consumer protection is emerging but niche.** Chris Pappas (D-NH)
[supports legislation](https://chrispappas.org/2026/03/chris-pappas-for-senate-highlights-actions-to-lower-grocery-costs-for-granite-state-families/)
to ban AI-powered personalized price gouging. Roy Cooper (D-NC) wants to
[prohibit](https://roycooper.com/make-stuff-cost-less) algorithmic price
coordination in grocery stores. Booker wants to ban AI-powered price manipulation
in housing and groceries. These are early signals of a potential consumer-facing
AI issue — but so far, only Democrats are raising it.

**AI and healthcare, AI and agriculture** — topics with enormous practical
implications — get almost no attention from either party.

---

### Eight Races to Watch

In eight states, **candidates from both parties** have AI positions, creating the
potential for genuine debate: **Alabama, Georgia, Illinois, Massachusetts, Maine,
Michigan, New Hampshire, and Texas**.

**Texas** is the most AI-engaged race overall (24 excerpts), driven by Talarico's
comprehensive platform. **Michigan** (18 excerpts) features a genuine clash:
Haley Stevens (D)
[helped write the CHIPS Act](https://haleyformi.com/about/) to bring chip
production to Michigan, while Mike Rogers (R)
[supports](https://rogersforsenate.com/news/rogers-applauds-white-house-ai-framework-that-establishes-global-leadership-and-protects-kids-online)
the White House AI framework — a rare race where both sides engage substantively
on AI, albeit from very different angles.

David Costello (D-ME) stands alone in framing AI as an
[existential risk](https://www.costelloforsenate.com/press-releases), listing
unconstrained AI alongside climate change and nuclear weapons as threats requiring
global mitigation — a frame no other leading candidate adopts.

---

### Methodology

This analysis is based on automated scraping and AI-assisted analysis of campaign
websites for 77 leading candidates in the 2026 U.S. Senate races (Class II seats).
Content was scraped from official campaign websites in March 2026 and analyzed
using Claude (Anthropic) to identify AI-relevant passages and classify them by
topic, sentiment, and confidence. "Leading candidates" includes incumbents,
primary frontrunners, and major declared challengers as identified via FEC filings
and Ballotpedia.

**Limitations:** This analysis captures only what candidates say on their campaign
websites — not floor speeches, committee testimony, interviews, or social media.
Some campaign sites are minimally developed or focus on fundraising rather than
policy. Incumbents' official Senate websites (.gov) may contain policy positions
not reflected in their campaign sites. AI-adjacent topics (automation, surveillance,
semiconductors) are included when contextually related to artificial intelligence,
which involves judgment calls in classification.

---

*Data and analysis available at this dashboard. Use the navigation to explore
by party, topic, candidate, or state.*
""")


# ═══════════════════════════════════════════════════════════════════
# BY PARTY
# ═══════════════════════════════════════════════════════════════════
elif page == "🏛️ By Party":
    st.title("AI Positions by Party")

    leading_only = st.toggle("Leading candidates only", value=False)
    tier_clause = "AND ca.candidate_tier = 'leading'" if leading_only else ""

    st.subheader("How Each Party Feels About AI")
    st.caption("Click a bar segment to see those excerpts")
    party_sent = query_df(f"""
        SELECT ca.party, e.sentiment, COUNT(*) as count
        FROM excerpts e JOIN candidates ca ON e.candidate_id = ca.id
        WHERE ca.party IN ('DEM', 'REP') {tier_clause}
        GROUP BY ca.party, e.sentiment
    """)
    if not party_sent.empty:
        party_sent["party_label"] = party_sent["party"].map({"DEM": "Democrat", "REP": "Republican"})
        fig = px.bar(party_sent, x="party_label", y="count", color="sentiment",
                     color_discrete_map=SENTIMENT_COLORS, barmode="stack",
                     custom_data=["party", "sentiment"])
        fig.update_layout(height=350, xaxis_title="", yaxis_title="Number of excerpts",
                          margin=dict(l=0, r=20, t=10, b=20))
        event = st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG, on_select="rerun", key="party_sent")
        if event and event.selection and event.selection.points:
            pt = event.selection.points[0]
            navigate("🔍 Search", party=pt["customdata"][0], sentiment=pt["customdata"][1])
            st.rerun()

    st.divider()

    st.subheader("Where the Parties Diverge")
    st.caption("Valence: +1 = entirely supportive, -1 = entirely opposed. Click a cell to explore.")
    topic_party = query_df(f"""
        SELECT t.name as tag, ca.party, e.sentiment, COUNT(*) as count
        FROM excerpts e
        JOIN candidates ca ON e.candidate_id = ca.id
        JOIN excerpt_tags et ON e.id = et.excerpt_id
        JOIN tags t ON et.tag_id = t.id
        WHERE ca.party IN ('DEM', 'REP') {tier_clause}
        GROUP BY t.name, ca.party, e.sentiment HAVING count >= 1
    """)
    if not topic_party.empty:
        valence_map = {"supportive": 1, "cautious": 0, "opposed": -1, "neutral": 0, "mixed": 0}
        topic_party["valence"] = topic_party["sentiment"].map(valence_map) * topic_party["count"]
        agg = topic_party.groupby(["tag", "party"]).agg(
            total=("count", "sum"), valence=("valence", "sum")).reset_index()
        agg["score"] = agg["valence"] / agg["total"]
        agg["label"] = agg["tag"].apply(fmt_tag)
        agg = agg[agg["total"] >= 2]

        pivot = agg.pivot(index="label", columns="party", values="score").fillna(0)
        pivot = pivot.rename(columns={"DEM": "Democrat", "REP": "Republican"})
        if "Democrat" in pivot.columns and "Republican" in pivot.columns:
            pivot["gap"] = abs(pivot["Democrat"] - pivot["Republican"])
            pivot = pivot.sort_values("gap", ascending=True).drop(columns="gap")

        # Store tag mapping for click-through
        label_to_tag = dict(zip(agg["label"], agg["tag"]))

        fig = px.imshow(pivot, color_continuous_scale="RdBu", color_continuous_midpoint=0,
                        labels=dict(color="Valence"), aspect="auto")
        fig.update_layout(height=max(350, len(pivot) * 35), margin=dict(l=0, r=20, t=10, b=20))
        event = st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG, on_select="rerun", key="party_heatmap")
        if event and event.selection and event.selection.points:
            pt = event.selection.points[0]
            clicked_label = pivot.index[pt["y"]] if isinstance(pt.get("y"), int) else pt.get("y")
            clicked_party_label = pivot.columns[pt["x"]] if isinstance(pt.get("x"), int) else pt.get("x")
            clicked_tag = label_to_tag.get(clicked_label)
            clicked_party = "DEM" if clicked_party_label == "Democrat" else "REP"
            if clicked_tag:
                navigate("🔍 Search", tag=clicked_tag, party=clicked_party)
                st.rerun()

    st.divider()

    st.subheader("Topic Frequency by Party")
    st.caption("Click a bar to explore that topic")
    tag_counts = query_df(f"""
        SELECT t.name as tag, ca.party, COUNT(*) as count
        FROM excerpts e
        JOIN candidates ca ON e.candidate_id = ca.id
        JOIN excerpt_tags et ON e.id = et.excerpt_id
        JOIN tags t ON et.tag_id = t.id
        WHERE ca.party IN ('DEM', 'REP') {tier_clause}
        GROUP BY t.name, ca.party ORDER BY count DESC
    """)
    if not tag_counts.empty:
        tag_counts["label"] = tag_counts["tag"].apply(fmt_tag)
        tag_counts["party_label"] = tag_counts["party"].map({"DEM": "Democrat", "REP": "Republican"})
        fig = px.bar(tag_counts, x="count", y="label", color="party_label",
                     color_discrete_map=PARTY_COLORS, barmode="group", orientation="h",
                     custom_data=["tag", "party"])
        fig.update_layout(yaxis=dict(autorange="reversed", categoryorder="total ascending"),
                          height=max(400, len(tag_counts["label"].unique()) * 35),
                          margin=dict(l=0, r=20, t=10, b=20), legend_title="Party")
        fig.update_xaxes(title="Mentions")
        fig.update_yaxes(title="")
        event = st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG, on_select="rerun", key="party_topics")
        if event and event.selection and event.selection.points:
            pt = event.selection.points[0]
            navigate("🏷️ By Topic", tag=pt["customdata"][0])
            st.rerun()


# ═══════════════════════════════════════════════════════════════════
# BY TOPIC
# ═══════════════════════════════════════════════════════════════════
elif page == "🏷️ By Topic":
    st.title("AI Positions by Topic")

    all_tags = query_df("""
        SELECT t.name, COUNT(*) as count FROM excerpt_tags et JOIN tags t ON et.tag_id = t.id
        GROUP BY t.name ORDER BY count DESC
    """)

    if all_tags.empty:
        st.warning("No analyzed excerpts yet.")
    else:
        # Pre-select tag if navigated from another page
        nav_tag = get_nav("tag")
        tag_list = all_tags["name"].tolist()
        default_idx = tag_list.index(nav_tag) if nav_tag and nav_tag in tag_list else 0

        selected_tag = st.selectbox(
            "Select a topic", tag_list, index=default_idx,
            format_func=lambda t: f"{fmt_tag(t)} ({all_tags[all_tags['name']==t]['count'].values[0]} mentions)")

        if selected_tag:
            excerpts = query_df("""
                SELECT ca.id as cand_id, ca.name, ca.party, ca.state, ca.candidate_tier,
                       e.excerpt_text, e.position_summary, e.sentiment, e.confidence,
                       c.source_url, GROUP_CONCAT(DISTINCT t2.name) as tags
                FROM excerpts e
                JOIN candidates ca ON e.candidate_id = ca.id
                JOIN content c ON e.content_id = c.id
                JOIN excerpt_tags et ON e.id = et.excerpt_id
                JOIN tags t ON et.tag_id = t.id
                LEFT JOIN excerpt_tags et2 ON e.id = et2.excerpt_id
                LEFT JOIN tags t2 ON et2.tag_id = t2.id
                WHERE t.name = ?
                GROUP BY e.id
                ORDER BY ca.candidate_tier DESC, e.confidence DESC
            """, [selected_tag])

            c1, c2, c3 = st.columns(3)
            c1.metric("Mentions", len(excerpts))
            c2.metric("Candidates", excerpts["name"].nunique())
            sent_counts = excerpts["sentiment"].value_counts()
            c3.metric("Dominant Sentiment", (sent_counts.index[0] if len(sent_counts) > 0 else "N/A").title())

            col1, col2 = st.columns(2)
            with col1:
                st.caption("Click a bar to filter by sentiment")
                sent_df = excerpts["sentiment"].value_counts().reset_index()
                sent_df.columns = ["sentiment", "count"]
                fig = px.bar(sent_df, x="sentiment", y="count", color="sentiment",
                             color_discrete_map=SENTIMENT_COLORS, custom_data=["sentiment"])
                fig.update_layout(showlegend=False, height=250, margin=dict(l=0, r=0, t=10, b=20))
                event = st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG, on_select="rerun", key="topic_sent_chart")
                clicked_sentiment = None
                if event and event.selection and event.selection.points:
                    clicked_sentiment = event.selection.points[0]["customdata"][0]
            with col2:
                party_df = excerpts.groupby(["party", "sentiment"]).size().reset_index(name="count")
                party_df = party_df[party_df["party"].isin(["DEM", "REP"])]
                if not party_df.empty:
                    st.caption("Click a segment to filter by party + sentiment")
                    fig = px.bar(party_df, x="party", y="count", color="sentiment",
                                 color_discrete_map=SENTIMENT_COLORS, barmode="stack",
                                 custom_data=["party", "sentiment"])
                    fig.update_layout(height=250, margin=dict(l=0, r=0, t=10, b=20),
                                      xaxis_title="", showlegend=False)
                    event2 = st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG, on_select="rerun", key="topic_party_chart")
                    clicked_party_sent = None
                    if event2 and event2.selection and event2.selection.points:
                        pt = event2.selection.points[0]
                        clicked_party_sent = (pt["customdata"][0], pt["customdata"][1])

            st.divider()

            # Pre-populate filters from chart clicks
            default_sent = [clicked_sentiment] if clicked_sentiment else []
            default_party = [clicked_party_sent[0]] if locals().get("clicked_party_sent") else []
            if locals().get("clicked_party_sent") and not clicked_sentiment:
                default_sent = [clicked_party_sent[1]]

            col1, col2, col3 = st.columns(3)
            party_filter = col1.multiselect("Party", sorted(excerpts["party"].unique().tolist()), default=default_party)
            sent_filter = col2.multiselect("Sentiment", sorted(excerpts["sentiment"].unique().tolist()), default=default_sent)
            leading_only = col3.toggle("Leading candidates only", value=False, key="topic_leading")

            filtered = excerpts
            if party_filter:
                filtered = filtered[filtered["party"].isin(party_filter)]
            if sent_filter:
                filtered = filtered[filtered["sentiment"].isin(sent_filter)]
            if leading_only:
                filtered = filtered[filtered["candidate_tier"] == "leading"]

            st.subheader(f"Positions ({len(filtered)})")
            render_excerpts(filtered, show_candidate=True)


# ═══════════════════════════════════════════════════════════════════
# BY CANDIDATE
# ═══════════════════════════════════════════════════════════════════
elif page == "👤 By Candidate":
    st.title("AI Positions by Candidate")

    tier_filter = st.radio("Show", [
        "Leading candidates only",
        "All with AI positions",
        "All leading (including no AI content)",
    ], horizontal=True)

    if tier_filter == "All leading (including no AI content)":
        cand_df = query_df("""
            SELECT ca.id, ca.name, ca.party, ca.state, ca.campaign_url, ca.candidate_tier,
                   (SELECT COUNT(*) FROM excerpts WHERE candidate_id = ca.id) as excerpt_count
            FROM candidates ca WHERE ca.candidate_tier = 'leading'
            ORDER BY ca.state, ca.name
        """)
    elif tier_filter == "Leading candidates only":
        cand_df = query_df("""
            SELECT ca.id, ca.name, ca.party, ca.state, ca.campaign_url, ca.candidate_tier,
                   COUNT(e.id) as excerpt_count
            FROM candidates ca JOIN excerpts e ON e.candidate_id = ca.id
            WHERE ca.candidate_tier = 'leading'
            GROUP BY ca.id ORDER BY ca.state, ca.name
        """)
    else:
        cand_df = query_df("""
            SELECT ca.id, ca.name, ca.party, ca.state, ca.campaign_url, ca.candidate_tier,
                   COUNT(e.id) as excerpt_count
            FROM candidates ca JOIN excerpts e ON e.candidate_id = ca.id
            GROUP BY ca.id ORDER BY ca.candidate_tier DESC, ca.state, ca.name
        """)

    if cand_df.empty:
        st.warning("No candidates found for this filter.")
    else:
        states = ["All states"] + sorted(cand_df["state"].unique().tolist())
        state_filter = st.selectbox("Filter by state", states)
        display_df = cand_df[cand_df["state"] == state_filter] if state_filter != "All states" else cand_df

        # Pre-select candidate if navigated from another page
        nav_cand_id = get_nav("candidate_id")
        default_idx = 0
        if nav_cand_id:
            matches = display_df.index[display_df["id"] == nav_cand_id].tolist()
            if matches:
                default_idx = display_df.index.get_loc(matches[0])
                if hasattr(default_idx, '__index__'):
                    default_idx = default_idx.__index__()

        cand_options = display_df.apply(
            lambda r: f"{'⭐ ' if r.get('candidate_tier') == 'leading' else ''}{r['name']} ({r['party']}, {r['state']}) — {r['excerpt_count']} excerpts",
            axis=1).tolist()

        if not cand_options:
            st.info("No candidates match this filter.")
        else:
            selected_idx = st.selectbox("Select a candidate", range(len(cand_options)),
                                         index=min(default_idx, len(cand_options) - 1),
                                         format_func=lambda i: cand_options[i])
            selected = display_df.iloc[selected_idx]

            tier_badge = "⭐ Leading Candidate  ·  " if selected.get("candidate_tier") == "leading" else ""
            st.header(f"{selected['name']} ({selected['party']}, {selected['state']})")
            url_link = f"[{selected['campaign_url']}]({selected['campaign_url']})" if selected["campaign_url"] else "No URL"
            st.caption(f"{tier_badge}🌐 {url_link}")

            excerpts = query_df("""
                SELECT e.excerpt_text, e.position_summary, e.sentiment, e.confidence,
                       c.source_url, c.title as page_title,
                       GROUP_CONCAT(t.name, ', ') as tags
                FROM excerpts e
                JOIN content c ON e.content_id = c.id
                LEFT JOIN excerpt_tags et ON e.id = et.excerpt_id
                LEFT JOIN tags t ON et.tag_id = t.id
                WHERE e.candidate_id = ?
                GROUP BY e.id ORDER BY e.confidence DESC
            """, [int(selected["id"])])

            if excerpts.empty:
                st.info("No AI-related content found on this candidate's website.")
            else:
                # Generate overview summary from excerpts
                summary = build_candidate_summary(selected, excerpts)
                st.markdown(summary)

                st.divider()
                col1, col2 = st.columns(2)
                with col1:
                    st.subheader("Sentiment")
                    sent = excerpts["sentiment"].value_counts().reset_index()
                    sent.columns = ["sentiment", "count"]
                    fig = px.pie(sent, values="count", names="sentiment",
                                 color="sentiment", color_discrete_map=SENTIMENT_COLORS, hole=0.45)
                    fig.update_traces(textposition="outside", textinfo="label+value")
                    fig.update_layout(height=280, margin=dict(l=0, r=0, t=10, b=0), showlegend=False)
                    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

                with col2:
                    st.subheader("Topics")
                    tag_list = []
                    for tags_str in excerpts["tags"].dropna():
                        tag_list.extend([t.strip() for t in tags_str.split(",")])
                    if tag_list:
                        tc = pd.Series(tag_list).value_counts().reset_index()
                        tc.columns = ["tag", "count"]
                        tc["label"] = tc["tag"].apply(fmt_tag)
                        fig = px.bar(tc, x="count", y="label", orientation="h",
                                     color="count", color_continuous_scale="Blues",
                                     custom_data=["tag"])
                        fig.update_layout(yaxis=dict(autorange="reversed"), showlegend=False,
                                          coloraxis_showscale=False, height=280,
                                          margin=dict(l=0, r=20, t=10, b=0))
                        fig.update_yaxes(title="")
                        event = st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG, on_select="rerun", key="cand_tags")
                        if event and event.selection and event.selection.points:
                            clicked_tag = event.selection.points[0]["customdata"][0]
                            navigate("🏷️ By Topic", tag=clicked_tag)
                            st.rerun()

                st.divider()
                st.subheader("All Positions")
                render_excerpts(excerpts, show_candidate=False)


# ═══════════════════════════════════════════════════════════════════
# BY STATE
# ═══════════════════════════════════════════════════════════════════
elif page == "🗺️ By State":
    st.title("AI Positions by State")

    state_data = query_df("""
        SELECT ca.state,
               COUNT(DISTINCT ca.id) as leading_candidates,
               COUNT(DISTINCT CASE WHEN e.id IS NOT NULL THEN ca.id END) as with_ai,
               COUNT(e.id) as excerpts
        FROM candidates ca
        LEFT JOIN excerpts e ON e.candidate_id = ca.id
        WHERE ca.candidate_tier = 'leading'
        GROUP BY ca.state HAVING leading_candidates > 0
        ORDER BY ca.state
    """)

    if state_data.empty:
        st.warning("No state data available.")
    else:
        nav_state = get_nav("state")
        state_list = state_data["state"].tolist()
        default_idx = state_list.index(nav_state) if nav_state and nav_state in state_list else 0

        selected_state = st.selectbox("Select a state", state_list, index=default_idx,
            format_func=lambda s: f"{s} — {state_data[state_data['state']==s]['leading_candidates'].values[0]} leading, {state_data[state_data['state']==s]['excerpts'].values[0]} AI excerpts")

        if selected_state:
            state_cands = query_df("""
                SELECT ca.id, ca.name, ca.party, ca.candidate_tier, ca.campaign_url,
                       COUNT(e.id) as excerpts
                FROM candidates ca
                LEFT JOIN excerpts e ON e.candidate_id = ca.id
                WHERE ca.state = ? AND ca.candidate_tier = 'leading'
                GROUP BY ca.id ORDER BY excerpts DESC
            """, [selected_state])

            st.subheader(f"Leading Candidates in {selected_state}")

            # Clickable candidate list
            cols = st.columns(min(len(state_cands), 4))
            for i, (_, row) in enumerate(state_cands.iterrows()):
                with cols[i % len(cols)]:
                    ai_label = f"{row['excerpts']} AI excerpts" if row["excerpts"] > 0 else "No AI content"
                    party_emoji = "🔵" if row["party"] == "DEM" else "🔴" if row["party"] == "REP" else "🟢"
                    if st.button(f"{party_emoji} {row['name']}\n{ai_label}", key=f"state_cand_{row['id']}",
                                 use_container_width=True):
                        navigate("👤 By Candidate", candidate_id=int(row["id"]))
                        st.rerun()

            st.divider()

            state_excerpts = query_df("""
                SELECT ca.name, ca.party, ca.state, ca.candidate_tier,
                       e.excerpt_text, e.position_summary, e.sentiment, e.confidence,
                       c.source_url, GROUP_CONCAT(t.name, ', ') as tags
                FROM excerpts e
                JOIN candidates ca ON e.candidate_id = ca.id
                JOIN content c ON e.content_id = c.id
                LEFT JOIN excerpt_tags et ON e.id = et.excerpt_id
                LEFT JOIN tags t ON et.tag_id = t.id
                WHERE ca.state = ? AND ca.candidate_tier = 'leading'
                GROUP BY e.id ORDER BY ca.name, e.confidence DESC
            """, [selected_state])

            if not state_excerpts.empty:
                st.subheader(f"AI Positions in {selected_state}")
                render_excerpts(state_excerpts, show_candidate=True)
            else:
                st.info(f"No AI-related content from leading candidates in {selected_state}.")


# ═══════════════════════════════════════════════════════════════════
# SEARCH
# ═══════════════════════════════════════════════════════════════════
elif page == "🔍 Search":
    st.title("Search")

    # Pick up any navigation context
    nav_sentiment = get_nav("sentiment")
    nav_party = get_nav("party")
    nav_tag = get_nav("tag")

    # If we arrived with context, show filtered excerpts directly
    if nav_sentiment or (nav_party and nav_tag):
        st.subheader("Filtered Results")

        sql = """
            SELECT ca.name, ca.party, ca.state, ca.candidate_tier,
                   e.excerpt_text, e.position_summary, e.sentiment, e.confidence,
                   c.source_url, GROUP_CONCAT(DISTINCT t.name) as tags
            FROM excerpts e
            JOIN candidates ca ON e.candidate_id = ca.id
            JOIN content c ON e.content_id = c.id
            LEFT JOIN excerpt_tags et ON e.id = et.excerpt_id
            LEFT JOIN tags t ON et.tag_id = t.id
            WHERE 1=1
        """
        params = []
        filters = []

        if nav_sentiment:
            sql += " AND e.sentiment = ?"
            params.append(nav_sentiment)
            filters.append(f"Sentiment: **{nav_sentiment}**")
        if nav_party:
            sql += " AND ca.party = ?"
            params.append(nav_party)
            filters.append(f"Party: **{nav_party}**")
        if nav_tag:
            sql += " AND e.id IN (SELECT et2.excerpt_id FROM excerpt_tags et2 JOIN tags t2 ON et2.tag_id = t2.id WHERE t2.name = ?)"
            params.append(nav_tag)
            filters.append(f"Topic: **{fmt_tag(nav_tag)}**")

        sql += " GROUP BY e.id ORDER BY ca.candidate_tier DESC, e.confidence DESC LIMIT 50"

        st.markdown("Filters: " + "  ·  ".join(filters))
        results = query_df(sql, params)
        st.caption(f"{len(results)} results")
        render_excerpts(results, show_candidate=True)

        st.divider()

    search_type = st.radio("Search mode", ["Keyword search", "Tag filter"], horizontal=True)

    if search_type == "Keyword search":
        query_text = st.text_input("Search all scraped content", placeholder="e.g. artificial intelligence, deepfake, automation")

        col1, col2 = st.columns(2)
        party = col1.selectbox("Party", ["All", "DEM", "REP"], key="kw_party")
        leading_only = col2.toggle("Leading candidates only", value=False, key="kw_leading")

        if query_text:
            sql = """
                SELECT ca.name, ca.party, ca.state, ca.candidate_tier, c.source_url, c.title,
                       snippet(content_fts, 1, '**', '**', '...', 50) as snippet
                FROM content_fts
                JOIN content c ON content_fts.rowid = c.id
                JOIN candidates ca ON c.candidate_id = ca.id
                WHERE content_fts MATCH ?
            """
            params = [query_text]
            if party != "All":
                sql += " AND ca.party = ?"
                params.append(party)
            if leading_only:
                sql += " AND ca.candidate_tier = 'leading'"
            sql += " ORDER BY rank LIMIT 30"

            results = query_df(sql, params)
            st.subheader(f"{len(results)} results")
            for _, row in results.iterrows():
                star = "⭐ " if row.get("candidate_tier") == "leading" else ""
                with st.expander(f"{star}{row['name']} ({row['party']}, {row['state']}) — {(row['title'] or '')[:50]}"):
                    st.markdown(f"...{row['snippet']}...")
                    st.caption(f"[Source →]({row['source_url']})")

    elif search_type == "Tag filter":
        all_tags = query_df("""
            SELECT t.name, COUNT(*) as count FROM excerpt_tags et JOIN tags t ON et.tag_id = t.id
            GROUP BY t.name ORDER BY count DESC
        """)

        if not all_tags.empty:
            selected_tags = st.multiselect(
                "Select topics", all_tags["name"].tolist(),
                format_func=lambda t: f"{fmt_tag(t)} ({all_tags[all_tags['name']==t]['count'].values[0]})")

            col1, col2, col3 = st.columns(3)
            party = col1.selectbox("Party", ["All", "DEM", "REP"], key="tag_party")
            sentiment = col2.selectbox("Sentiment", ["All"] + list(SENTIMENT_COLORS.keys()), key="tag_sent")
            leading_only = col3.toggle("Leading only", value=False, key="tag_leading")

            if selected_tags:
                placeholders = ",".join("?" * len(selected_tags))
                sql = f"""
                    SELECT ca.name, ca.party, ca.state, ca.candidate_tier,
                           e.excerpt_text, e.position_summary, e.sentiment, e.confidence,
                           c.source_url, GROUP_CONCAT(DISTINCT t.name) as tags
                    FROM excerpts e
                    JOIN candidates ca ON e.candidate_id = ca.id
                    JOIN content c ON e.content_id = c.id
                    JOIN excerpt_tags et ON e.id = et.excerpt_id
                    JOIN tags t ON et.tag_id = t.id
                    WHERE t.name IN ({placeholders})
                """
                params = list(selected_tags)
                if party != "All":
                    sql += " AND ca.party = ?"
                    params.append(party)
                if sentiment != "All":
                    sql += " AND e.sentiment = ?"
                    params.append(sentiment)
                if leading_only:
                    sql += " AND ca.candidate_tier = 'leading'"
                sql += " GROUP BY e.id ORDER BY ca.candidate_tier DESC, e.confidence DESC LIMIT 50"

                results = query_df(sql, params)
                st.subheader(f"{len(results)} results")
                render_excerpts(results, show_candidate=True)


# ═══════════════════════════════════════════════════════════════════
# FEEDBACK
# ═══════════════════════════════════════════════════════════════════
elif page == "💡 Feedback":
    st.title("Help Us Improve This Dashboard")

    st.markdown("""
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                padding: 30px; border-radius: 12px; color: white; margin-bottom: 24px;">
        <h2 style="color: white; margin-top: 0;">We want your ideas!</h2>
        <p style="font-size: 1.1em; margin-bottom: 0;">
            This is a living project tracking how 2026 Senate candidates talk about AI.
            What would make it more useful to you? New features, better visualizations,
            missing candidates, data corrections — we want to hear it all.
        </p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)
    col1.markdown("**🔧 Feature Ideas**\n\nNew views, filters, comparisons, exports — what would help you explore the data?")
    col2.markdown("**📊 Data Gaps**\n\nKnow a candidate's AI position we're missing? A page we didn't scrape? Let us know.")
    col3.markdown("**🐛 Bug Reports**\n\nSomething broken or displaying incorrectly? Help us fix it.")

    st.divider()

    with st.form("feedback_form", clear_on_submit=True):
        req_type = st.selectbox("What kind of feedback?", ["Feature request", "Data correction", "Bug report", "Other"])
        title = st.text_input("Summary", placeholder="e.g. Add side-by-side comparison for two candidates")
        description = st.text_area("Tell us more", placeholder="What would you like to see? What's missing or broken? The more detail, the better.", height=150)
        email = st.text_input("Your email (optional)", placeholder="In case we want to follow up")
        submitted = st.form_submit_button("Submit Feedback", type="primary")

    if submitted:
        if not title or not description:
            st.error("Please fill in both a title and description.")
        else:
            import urllib.parse
            # Build a GitHub issue URL with pre-filled content
            label_map = {
                "Feature request": "enhancement",
                "Bug report": "bug",
                "Data correction": "data",
                "Other": "question",
            }
            body = f"**Type:** {req_type}\n\n{description}"
            if email:
                body += f"\n\n**Contact:** {email}"
            body += "\n\n---\n*Submitted via the dashboard feedback form.*"

            # Try GitHub API if token is available (creates issue directly)
            gh_token = None
            try:
                gh_token = st.secrets.get("GITHUB_TOKEN")
            except Exception:
                pass

            if gh_token:
                import requests
                resp = requests.post(
                    f"https://api.github.com/repos/{GITHUB_REPO}/issues",
                    headers={"Authorization": f"token {gh_token}", "Accept": "application/vnd.github.v3+json"},
                    json={
                        "title": f"[{req_type}] {title}",
                        "body": body,
                        "labels": [label_map.get(req_type, "question")],
                    },
                )
                if resp.status_code == 201:
                    issue_url = resp.json().get("html_url", "")
                    st.success(f"Thanks! Your feedback has been submitted. [View it on GitHub]({issue_url})")
                else:
                    st.error("Something went wrong submitting your feedback. Please try the link below instead.")
                    params = urllib.parse.urlencode({"title": f"[{req_type}] {title}", "body": body})
                    st.markdown(f"[Submit on GitHub →](https://github.com/{GITHUB_REPO}/issues/new?{params})")
            else:
                # Fallback: open a pre-filled GitHub issue URL
                params = urllib.parse.urlencode({
                    "title": f"[{req_type}] {title}",
                    "body": body,
                    "labels": label_map.get(req_type, "question"),
                })
                issue_url = f"https://github.com/{GITHUB_REPO}/issues/new?{params}"
                st.success("Thanks! Click the link below to submit your feedback on GitHub:")
                st.markdown(f"### [Submit on GitHub →]({issue_url})")
                st.caption("You'll need a GitHub account. Your title and description will be pre-filled.")
