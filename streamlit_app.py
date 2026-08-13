"""Streamlit frontend for FinQuery.

Connects to the FastAPI backend (api.py) running on localhost:8000.

Features
--------
- Login form with JWT authentication.
- Question input with real-time workflow step display.
- Answer panel with source citations.
- Per-user rate limit feedback.

Run (after starting the FastAPI backend):
    streamlit run streamlit_app.py
"""

import os
import time
from pathlib import Path

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="FinQuery — Infosys Financial Q&A",
    page_icon="📊",
    layout="centered",
)

# ---------------------------------------------------------------------------
# Session state initialisation
# ---------------------------------------------------------------------------
if "token" not in st.session_state:
    st.session_state.token = None
if "username" not in st.session_state:
    st.session_state.username = ""
if "history" not in st.session_state:
    st.session_state.history = []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _auth_header() -> dict[str, str]:
    return {"Authorization": f"Bearer {st.session_state.token}"}


def _login(username: str, password: str) -> bool:
    """POST credentials to /auth/token; store token on success."""
    try:
        resp = requests.post(
            f"{API_BASE}/auth/token",
            data={"username": username, "password": password},
            timeout=10,
        )
    except requests.ConnectionError:
        st.error("Cannot connect to the API. Make sure `uvicorn api:app` is running.")
        return False

    if resp.status_code == 200:
        st.session_state.token    = resp.json()["access_token"]
        st.session_state.username = username
        return True

    detail = resp.json().get("detail", "Login failed.")
    st.error(detail)
    return False


def _send_query(question: str) -> dict | None:
    """POST a question to /query; return the JSON response or None on error."""
    try:
        resp = requests.post(
            f"{API_BASE}/query",
            json={"question": question},
            headers=_auth_header(),
            timeout=120,
        )
    except requests.ConnectionError:
        st.error("Cannot connect to the API.")
        return None

    if resp.status_code == 429:
        try:
            detail = resp.json().get("detail", "Rate limit exceeded.")
        except Exception:
            detail = "Rate limit exceeded."
        st.warning(detail)
        return None
    if resp.status_code == 401:
        st.session_state.token = None
        st.warning("Session expired. Please log in again.")
        st.rerun()
        return None
    if resp.status_code != 200:
        try:
            detail = resp.json().get("detail", "Unknown error")
        except Exception:
            detail = resp.text[:300] if resp.text else f"HTTP {resp.status_code}"
        st.error(f"API error {resp.status_code}: {detail}")
        return None

    return resp.json()


# ---------------------------------------------------------------------------
# Login page
# ---------------------------------------------------------------------------

def _show_login() -> None:
    st.title("📊 FinQuery")
    st.subheader("Infosys Financial Q&A")
    st.markdown("---")

    with st.form("login_form"):
        username = st.text_input("Username", placeholder="Enter username")
        password = st.text_input("Password", type="password", placeholder="Enter password")
        submitted = st.form_submit_button("Log in", use_container_width=True)

    if submitted:
        if not username or not password:
            st.warning("Please enter both username and password.")
        else:
            with st.spinner("Authenticating…"):
                if _login(username, password):
                    st.rerun()

    st.markdown(
        "<p style='font-size:0.8em;color:gray;'>Powered by OpenAI + ChromaDB + "
        "Numeric Fidelity Layer</p>",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Main app page
# ---------------------------------------------------------------------------

def _show_app() -> None:
    # Lighten textarea placeholder and enlarge its label.
    st.markdown(
        """<style>
        textarea::placeholder { color: #b0b8c1 !important; opacity: 1; }
        div[data-testid="stTextArea"] label p { font-size: 1.15rem !important; font-weight: 600; }
        </style>""",
        unsafe_allow_html=True,
    )
    # Header.
    col_title, col_logout = st.columns([4, 1])
    with col_title:
        st.title("📊 FinQuery")
    with col_logout:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Log out", use_container_width=True):
            st.session_state.token    = None
            st.session_state.username = ""
            st.session_state.history  = []
            st.rerun()

    st.caption(f"Signed in as **{st.session_state.username}**")
    st.markdown("---")

    # Question input.
    with st.form("query_form", clear_on_submit=True):
        question = st.text_area(
            "Ask a financial question about Infosys:",
            placeholder=(
                "Numerical  — What was Infosys voluntary attrition rate for IT Services in Q1 FY26?\n"
                "Descriptive — How is AI-related revenue growth offsetting compression in Infosys's traditional IT services?"
            ),
            height=100,
        )
        submitted = st.form_submit_button("Ask", use_container_width=True)

    if submitted and question.strip():
        _run_query(question.strip())

    # Show history (most recent first).
    if st.session_state.history:
        st.markdown("---")
        st.subheader("Previous questions")
        for entry in reversed(st.session_state.history):
            with st.expander(f"Q: {entry['question'][:80]}…" if len(entry['question']) > 80 else f"Q: {entry['question']}"):
                _render_result(entry)


def _run_query(question: str) -> None:
    """Send *question* to the API and display the result."""
    st.markdown("---")

    # Always show the submitted question so it stays visible after form clears.
    st.markdown(f"**Q: {question}**")

    with st.spinner("Waiting for API response…"):
        result = _send_query(question)

    if result is None:
        return

    route = result.get("route", "")
    route_badge = "🔢 Fact Database" if route == "FACT_DB" else "🔍 Vector Search"

    # Answer — prominently highlighted.
    st.success(result.get("answer", "No answer returned."))

    col_route, col_lat = st.columns(2)
    with col_route:
        st.caption(f"Pipeline: **{route_badge}**")
    with col_lat:
        st.caption(f"Latency: **{result.get('latency_ms', '—')} ms**")

    # Workflow steps — collapsed by default so they don't dominate the page.
    with st.expander("Pipeline steps"):
        for step in result.get("steps", []):
            st.markdown(
                f"✅ **Step {step['step']}: {step['name']}**  \n"
                f"&nbsp;&nbsp;&nbsp;&nbsp;{step['detail']}"
            )

    # SQL (if FACT_DB route).
    if route == "FACT_DB" and result.get("sql"):
        with st.expander("SQL query used"):
            st.code(result["sql"], language="sql")

    # Citations.
    citations = result.get("citations", [])
    if citations:
        with st.expander(f"Sources ({len(citations)})"):
            for i, citation in enumerate(citations, start=1):
                parts = Path(citation).parts
                display = "/".join(parts[-2:]) if len(parts) >= 2 else citation
                st.markdown(f"{i}. `{display}`")

    # Store in history.
    st.session_state.history.append(
        {"question": question, "result": result}
    )


def _render_result(entry: dict) -> None:
    """Render a previously stored result inside an expander."""
    result = entry.get("result", {})
    if not result:
        return

    route = result.get("route", "")
    route_badge = "🔢 Fact Database" if route == "FACT_DB" else "🔍 Vector Search"

    st.success(result.get("answer", "—"))
    st.caption(f"Pipeline: {route_badge} | Latency: {result.get('latency_ms', '—')} ms")

    with st.expander("Pipeline steps"):
        for step in result.get("steps", []):
            st.markdown(f"✅ **Step {step['step']}: {step['name']}** — {step['detail']}")

    citations = result.get("citations", [])
    if citations:
        with st.expander(f"Sources ({len(citations)})"):
            for citation in citations:
                parts = Path(citation).parts
                display = "/".join(parts[-2:]) if len(parts) >= 2 else citation
                st.caption(f"• {display}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    # Injected on every render (login page and app page) so the deploy button
    # never appears regardless of which page Streamlit is showing.
    st.markdown(
        """<style>
        [data-testid="stToolbarActions"] { display: none !important; }
        .stDeployButton { display: none !important; }
        #MainMenu { visibility: hidden; }
        footer { visibility: hidden; }
        </style>""",
        unsafe_allow_html=True,
    )
    if st.session_state.token is None:
        _show_login()
    else:
        _show_app()


if __name__ == "__main__":
    main()
else:
    # Streamlit runs this module as a script; ensure main() is called.
    main()
