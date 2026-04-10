import streamlit as st
import pandas as pd
import json
from sample_data import SAMPLE_TICKETS
from triage import triage_tickets
from kb import fetch_knowledge_base, format_kb_for_prompt

# ─── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="IT Helpdesk Triage Agent",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─── Styles ───────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&display=swap');

  html, body, [class*="css"] {
    font-family: 'IBM Plex Mono', monospace;
    background-color: #0A0A0F;
    color: #E2E8F0;
  }

  .stApp { background: #0A0A0F; }

  .metric-card {
    background: #0F172A;
    border: 1px solid #1E293B;
    border-radius: 8px;
    padding: 16px 20px;
    text-align: center;
  }
  .metric-value { font-size: 28px; font-weight: 700; color: #F1F5F9; }
  .metric-label { font-size: 10px; color: #64748B; letter-spacing: 0.15em; text-transform: uppercase; margin-top: 4px; }

  .badge-p1 { background: #7F1D1D; color: #FCA5A5; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }
  .badge-p2 { background: #7C2D12; color: #FED7AA; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }
  .badge-p3 { background: #1E3A5F; color: #93C5FD; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }
  .badge-p4 { background: #1E293B; color: #94A3B8; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }

  .section-label {
    font-size: 10px; color: #3B82F6; letter-spacing: 0.25em;
    text-transform: uppercase; margin-bottom: 8px;
  }

  .stButton > button {
    background: #3B82F6;
    color: white;
    border: none;
    font-family: 'IBM Plex Mono', monospace;
    font-weight: 600;
    border-radius: 6px;
    padding: 10px 24px;
  }
  .stButton > button:hover { background: #2563EB; }

  .dataframe { font-size: 12px !important; }
  .stDataFrame { border: 1px solid #1E293B; border-radius: 8px; overflow: hidden; }

  hr { border-color: #1E293B; }
</style>
""", unsafe_allow_html=True)

# ─── Header ───────────────────────────────────────────────────────────────────
st.markdown("""
<div style="padding: 32px 0 24px 0;">
  <div style="font-size:10px; color:#3B82F6; letter-spacing:0.25em; text-transform:uppercase; margin-bottom:10px;">
    IT Operations · AI-Powered
  </div>
  <h1 style="font-size:36px; font-weight:800; color:#F1F5F9; letter-spacing:-0.5px; margin:0;">
    Helpdesk Triage Agent
  </h1>
  <p style="color:#64748B; font-size:13px; margin-top:8px;">
    Batch-triage IT support tickets using Claude. Categorize · Prioritize · Route · Suggest actions.
  </p>
</div>
<hr>
""", unsafe_allow_html=True)

# ─── Input section ────────────────────────────────────────────────────────────
st.markdown('<div class="section-label">Input</div>', unsafe_allow_html=True)

input_mode = st.radio(
    "Data source",
    ["Sample Data (30 tickets)", "Upload CSV", "Paste JSON"],
    horizontal=True,
    label_visibility="collapsed",
)

tickets_to_triage = []

if input_mode == "Sample Data (30 tickets)":
    st.info(f"📋 **{len(SAMPLE_TICKETS)} tickets loaded** — real-world mix: Access & Auth, Hardware, Software, Network. Click Run Triage to process.")
    tickets_to_triage = SAMPLE_TICKETS

elif input_mode == "Upload CSV":
    st.markdown("**Required columns:** `id`, `subject`, `body`, `submitter`, `department`, `submitted_at`")
    uploaded = st.file_uploader("Upload ticket CSV", type=["csv"])
    if uploaded:
        df = pd.read_csv(uploaded)
        tickets_to_triage = df.to_dict(orient="records")
        st.success(f"✓ {len(tickets_to_triage)} tickets loaded from CSV")

elif input_mode == "Paste JSON":
    st.markdown("Paste a JSON array of ticket objects. Required fields: `id`, `subject`, `body`, `submitter`, `department`, `submitted_at`")
    raw_json = st.text_area("Ticket JSON", height=200, placeholder='[{"id": "TKT-001", "subject": "...", ...}]')
    if raw_json.strip():
        try:
            tickets_to_triage = json.loads(raw_json)
            st.success(f"✓ {len(tickets_to_triage)} tickets parsed")
        except json.JSONDecodeError as e:
            st.error(f"Invalid JSON: {e}")

st.markdown("---")

# ─── Run triage ───────────────────────────────────────────────────────────────
col_run, col_filter = st.columns([1, 3])

with col_run:
    run_clicked = st.button(
        f"⚡ Run Triage ({len(tickets_to_triage)} tickets)",
        disabled=len(tickets_to_triage) == 0,
        use_container_width=True,
    )

if run_clicked and tickets_to_triage:
    with st.spinner("Loading knowledge base + sending to Claude..."):
        try:
            kb_articles = fetch_knowledge_base()
            kb_block = format_kb_for_prompt(kb_articles)
            st.session_state["kb_articles"] = {a["id"][:8]: a for a in kb_articles}
            results = triage_tickets(tickets_to_triage, kb_block)
            st.session_state["triage_results"] = results
            st.session_state["source_tickets"] = {t["id"]: t for t in tickets_to_triage}
        except Exception as e:
            st.error(f"Triage failed: {e}")

# ─── Results ─────────────────────────────────────────────────────────────────
if "triage_results" in st.session_state:
    results = st.session_state["triage_results"]
    source = st.session_state.get("source_tickets", {})

    # ── Summary metrics ──
    st.markdown('<div class="section-label" style="margin-top:24px;">Summary</div>', unsafe_allow_html=True)

    total = len(results)
    p1_count = sum(1 for r in results if r["priority"].startswith("P1"))
    p2_count = sum(1 for r in results if r["priority"].startswith("P2"))
    auto_count = sum(1 for r in results if r.get("auto_resolvable"))
    kb_matched = sum(1 for r in results if r.get("kb_id"))
    auto_close_count = sum(1 for r in results if r.get("auto_close"))

    col1, col2, col3, col4, col5, col6 = st.columns(6)
    for col, val, label in [
        (col1, total, "Total Tickets"),
        (col2, p1_count, "P1 · Critical"),
        (col3, p2_count, "P2 · High"),
        (col4, total - p1_count - p2_count, "P3-P4 · Backlog"),
        (col5, kb_matched, "KB Matches"),
        (col6, auto_close_count, "Auto-Close Ready"),
    ]:
        with col:
            st.markdown(f"""
            <div class="metric-card">
              <div class="metric-value">{val}</div>
              <div class="metric-label">{label}</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("---")

    # ── Filters ──
    st.markdown('<div class="section-label">Filters</div>', unsafe_allow_html=True)
    fc1, fc2, fc3 = st.columns(3)

    all_cats = sorted(set(r["category"] for r in results))
    all_priorities = ["P1 - Critical", "P2 - High", "P3 - Medium", "P4 - Low"]
    all_owners = sorted(set(r["owner"] for r in results))

    with fc1:
        sel_cats = st.multiselect("Category", all_cats, default=all_cats)
    with fc2:
        sel_priorities = st.multiselect("Priority", all_priorities, default=all_priorities)
    with fc3:
        sel_owners = st.multiselect("Owner", all_owners, default=all_owners)

    filtered = [
        r for r in results
        if r["category"] in sel_cats
        and r["priority"] in sel_priorities
        and r["owner"] in sel_owners
    ]

    st.markdown(f"**{len(filtered)}** tickets match filters")
    st.markdown("---")

    # ── Triage table ──
    st.markdown('<div class="section-label">Triage Results</div>', unsafe_allow_html=True)

    kb_articles = st.session_state.get("kb_articles", {})

    for r in sorted(filtered, key=lambda x: x["priority"]):
        src = source.get(r["id"], {})
        priority = r["priority"]
        can_auto_close = r.get("auto_close", False)

        badge_class = {
            "P1 - Critical": "badge-p1",
            "P2 - High": "badge-p2",
            "P3 - Medium": "badge-p3",
            "P4 - Low": "badge-p4",
        }.get(priority, "badge-p4")

        label = f"{'✅ ' if can_auto_close else ''}{r['id']} · {src.get('subject', r['id'])} · {src.get('submitter', '')}"
        with st.expander(label):
            meta_col, action_col = st.columns([1, 2])

            with meta_col:
                st.markdown(f"**Priority:** <span class='{badge_class}'>{priority}</span>", unsafe_allow_html=True)
                st.markdown(f"**Category:** {r['category']}")
                st.markdown(f"**SLA:** {r['sla_hours']}h")
                st.markdown(f"**Owner:** {r['owner']}")
                st.markdown(f"**Auto-resolvable:** {'✓ Yes' if r.get('auto_resolvable') else '✗ No'}")
                if can_auto_close:
                    st.markdown('<span style="background:#14532D;color:#86EFAC;padding:3px 10px;border-radius:4px;font-size:11px;font-weight:600;">✅ AUTO-CLOSE READY</span>', unsafe_allow_html=True)
                tags = r.get("tags", [])
                if tags:
                    tag_html = " ".join(
                        f'<span style="background:#1E293B;color:#64748B;padding:2px 7px;border-radius:4px;font-size:10px;">{t}</span>'
                        for t in tags
                    )
                    st.markdown(f"**Tags:** {tag_html}", unsafe_allow_html=True)

            with action_col:
                # KB resolution block
                kb_id = r.get("kb_id")
                resolution = r.get("resolution")
                if kb_id and resolution:
                    kb_article = kb_articles.get(kb_id, {})
                    article_url = kb_article.get("article_url")
                    st.markdown("**Known Fix (KB Match):**")
                    st.success(resolution)
                    if article_url:
                        st.markdown(f"[📄 View KB Article →]({article_url})")
                    st.markdown("---")

                st.markdown("**Suggested Action:**")
                st.info(r["suggested_action"])
                if src.get("body"):
                    st.markdown("**Original ticket:**")
                    st.markdown(f'<div style="color:#64748B;font-size:12px;line-height:1.6;">{src["body"]}</div>', unsafe_allow_html=True)

    st.markdown("---")

    # ── Export ──
    st.markdown('<div class="section-label">Export</div>', unsafe_allow_html=True)

    export_rows = []
    for r in results:
        src = source.get(r["id"], {})
        export_rows.append({
            "Ticket ID": r["id"],
            "Subject": src.get("subject", ""),
            "Submitter": src.get("submitter", ""),
            "Department": src.get("department", ""),
            "Category": r["category"],
            "Priority": r["priority"],
            "SLA (hours)": r["sla_hours"],
            "Owner": r["owner"],
            "Auto-Resolvable": r.get("auto_resolvable", False),
            "Auto-Close": r.get("auto_close", False),
            "KB Match ID": r.get("kb_id") or "",
            "Resolution": r.get("resolution") or "",
            "Tags": ", ".join(r.get("tags", [])),
            "Suggested Action": r["suggested_action"],
        })

    df_export = pd.DataFrame(export_rows)
    csv_out = df_export.to_csv(index=False)

    st.download_button(
        label="↓ Download Triage Report (CSV)",
        data=csv_out,
        file_name="triage_report.csv",
        mime="text/csv",
    )
