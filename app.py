# Streamlit chatbot entry point — user-facing UI that talks to the LangGraph graph.
from dotenv import load_dotenv

load_dotenv()

from logging_config import setup_logging

setup_logging()

import streamlit as st

import graph_runner

st.set_page_config(page_title="JobMate AI", page_icon=":briefcase:")
st.title("JobMate AI")

if "thread_id" not in st.session_state:
    st.session_state.thread_id = graph_runner.new_thread_id()
if "messages" not in st.session_state:
    st.session_state.messages = []


def _render_job_list(jobs: list[dict]) -> None:
    for job in jobs:
        title = job.get("title", "Untitled")
        url = job.get("url", "")
        company = job.get("company", "")
        experience = job.get("experience_required", "")
        posted = job.get("posted_date", "")

        if url:
            st.markdown(f"**[{title}]({url})** — {company}")
        else:
            st.markdown(f"**{title}** — {company}")

        details = " | ".join(d for d in (experience, posted) if d)
        if details:
            st.caption(details)


def _render_message(msg: dict) -> None:
    with st.chat_message(msg["role"]):
        msg_type = msg.get("type", "text")
        if msg_type == "job_list":
            _render_job_list(msg["jobs"])
        elif msg_type == "empty":
            st.info(msg["text"])
        elif msg_type == "warning":
            st.warning(msg["text"])
        else:
            st.write(msg["text"])


def _build_assistant_messages(result: dict) -> list[dict]:
    messages: list[dict] = []
    status = result.get("status") or {}
    errors = status.get("errors") or []
    if errors:
        messages.append(
            {
                "role": "assistant",
                "type": "warning",
                "text": f"Note: ran into an issue during this request: {'; '.join(errors)}",
            }
        )

    intent = result.get("intent")
    filtered_jobs = result.get("filtered_jobs") or []

    if intent == "search":
        if filtered_jobs:
            messages.append({"role": "assistant", "type": "job_list", "jobs": filtered_jobs})
        else:
            messages.append(
                {"role": "assistant", "type": "empty", "text": "No matching jobs found for this search."}
            )
    elif intent == "open_urls":
        detail = status.get("detail")
        if detail:
            messages.append({"role": "assistant", "type": "text", "text": detail})
        else:
            messages.append(
                {
                    "role": "assistant",
                    "type": "empty",
                    "text": "Nothing to open — no prior search results in this session yet.",
                }
            )
    elif not errors:
        messages.append(
            {"role": "assistant", "type": "warning", "text": "Something went wrong processing that request."}
        )

    return messages


for message in st.session_state.messages:
    _render_message(message)

query = st.chat_input('Search for jobs, or say "open these urls" to open results from your last search')
if query:
    user_message = {"role": "user", "type": "text", "text": query}
    st.session_state.messages.append(user_message)
    _render_message(user_message)

    with st.spinner("Working on it..."):
        result = graph_runner.run_query(query, st.session_state.thread_id)

    assistant_messages = _build_assistant_messages(result)
    st.session_state.messages.extend(assistant_messages)
    for message in assistant_messages:
        _render_message(message)
