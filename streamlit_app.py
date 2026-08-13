import os

import requests
import streamlit as st


BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000/api/query")


st.set_page_config(page_title="Finance RAG Chat", page_icon="📊")
st.title("Finance Q&A Assistant")

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

with st.form("chat_form", clear_on_submit=True):
    user_question = st.text_area("Ask a question", height=120, placeholder="Example: What are Infosys revenue trends?")
    submitted = st.form_submit_button("Ask")

if submitted and user_question.strip():
    with st.spinner("Searching relevant documents and generating answer..."):
        try:
            response = requests.post(
                BACKEND_URL,
                json={"question": user_question.strip()},
                timeout=180,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:  # pragma: no cover - UI error handling
            st.error(f"Backend request failed: {exc}")
            st.stop()

    answer = payload.get("answer", "No answer returned.")
    citations = payload.get("citations", [])

    st.subheader("Answer")
    st.markdown(answer)

    if citations:
        st.subheader("Sources")
        for idx, citation in enumerate(citations, start=1):
            filename = citation.get("filename", "Unknown source")
            filepath = citation.get("filepath", "")
            score = citation.get("score")

            if filepath:
                source_text = f"{idx}. {filename}"
                if isinstance(score, (int, float)):
                    source_text += f" — score: {score:.3f}"
                st.markdown(f"- [{source_text}]({filepath})")
            else:
                text = f"{idx}. {filename}"
                if isinstance(score, (int, float)):
                    text += f" — score: {score:.3f}"
                st.markdown(f"- {text}")

    st.session_state.chat_history.append({
        "question": user_question.strip(),
        "answer": answer,
        "citations": citations,
    })

if st.session_state.chat_history:
    st.subheader("Recent conversation")
    for item in reversed(st.session_state.chat_history):
        st.markdown(f"**Q:** {item['question']}")
        st.markdown(f"**A:** {item['answer']}")
        if item.get("citations"):
            for idx, citation in enumerate(item["citations"], start=1):
                filename = citation.get("filename", "Unknown source")
                filepath = citation.get("filepath", "")
                if filepath:
                    st.markdown(f"- [{idx}. {filename}]({filepath})")
                else:
                    st.markdown(f"- {idx}. {filename}")
        st.markdown("---")
