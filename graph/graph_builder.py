# Builds and compiles the LangGraph StateGraph, wiring together the nodes in graph/nodes/.
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from graph.nodes import (
    ask_user,
    classify_intent,
    log_result,
    naukri_classify,
    naukri_search,
    open_urls,
    parse_query,
    route_platform,
)
from graph.state import GraphState


def _route_after_classify_intent(state: GraphState) -> str:
    # classify_intent sets state["intent"]; this just routes on it.
    intent = state.get("intent") or "search"
    return "open_urls" if intent == "open_urls" else "parse_query"


def build_graph(checkpointer=None):
    builder = StateGraph(GraphState)

    builder.add_node("classify_intent", classify_intent)
    builder.add_node("parse_query", parse_query)
    builder.add_node("route_platform", route_platform)
    builder.add_node("naukri_search", naukri_search)
    builder.add_node("naukri_classify", naukri_classify)
    builder.add_node("ask_user", ask_user)
    builder.add_node("open_urls", open_urls)
    builder.add_node("log_result", log_result)

    builder.add_edge(START, "classify_intent")
    builder.add_conditional_edges(
        "classify_intent",
        _route_after_classify_intent,
        {"parse_query": "parse_query", "open_urls": "open_urls"},
    )
    builder.add_edge("parse_query", "route_platform")
    builder.add_edge("route_platform", "naukri_search")
    builder.add_edge("naukri_search", "naukri_classify")
    builder.add_edge("naukri_classify", "ask_user")
    builder.add_edge("ask_user", "open_urls")
    builder.add_edge("open_urls", "log_result")
    builder.add_edge("log_result", END)

    return builder.compile(checkpointer=checkpointer or MemorySaver())
