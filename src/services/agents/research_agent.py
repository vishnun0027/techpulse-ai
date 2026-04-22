from langgraph.graph import StateGraph, END
from langchain_groq import ChatGroq
from typing import TypedDict, Annotated, List, Dict
import json
from supabase import Client
from loguru import logger
from pydantic import BaseModel, Field
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate

class ResearchState(TypedDict):
    article_text:   str
    article_title:  str
    user_id:        str
    embedding:      List[float]
    similar_history: List[Dict]
    web_context:    str
    final_summary:  str
    why_it_matters: str

class ResearchAnalysis(BaseModel):
    summary: str = Field(..., description="A 3-4 sentence summary of the article")
    why_it_matters: str = Field(..., description="One sentence explaining the significance")

def retrieve_history(state: ResearchState, supabase: Client) -> ResearchState:
    """Node 1: Pull top-3 related articles from Supabase pgvector."""
    try:
        result = supabase.rpc("match_articles", {
            "query_embedding": state["embedding"],
            "match_threshold": 0.72,
            "match_count": 3,
            "p_user_id": state["user_id"]
        }).execute()
        state["similar_history"] = result.data or []
    except Exception as e:
        logger.error(f"Retrieve history failed: {e}")
        state["similar_history"] = []
    return state

def build_summary(state: ResearchState, groq_api_key: str) -> ResearchState:
    """Node 2: RAG-enhanced summarization with historical context."""
    # Use higher capacity model for research and lower temperature for JSON stability
    llm = ChatGroq(model="llama-3.3-70b-versatile", api_key=groq_api_key, temperature=0.1)
    parser = JsonOutputParser(pydantic_object=ResearchAnalysis)

    history_context = ""
    if state.get("similar_history"):
        history_context = "\n".join([
            f"- [{r.get('published_at', 'recent')[:10]}] {r.get('title', 'Untitled')}: {r.get('why_it_matters', (r.get('summary') or '')[:120])}"
            for r in state["similar_history"]
        ])

    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a precise tech analyst. Summarize articles with historical context. {format_instructions}"),
        ("human", """HISTORICAL CONTEXT:
{history_context}

ARTICLE:
{article_title}
{article_text}""")
    ])

    chain = prompt | llm | parser

    try:
        result = chain.invoke({
            "history_context": history_context or "No prior coverage found.",
            "article_title": state["article_title"],
            "article_text": state["article_text"][:4000],
            "format_instructions": parser.get_format_instructions()
        })
        state["final_summary"]  = result.get("summary", "")
        state["why_it_matters"] = result.get("why_it_matters", "")
    except Exception as e:
        logger.error(f"Build summary failed: {e}")
        # Robust fallback
        state["final_summary"]  = f"Summary generation failed. Original start: {state['article_text'][:200]}..."
        state["why_it_matters"] = "Error in analysis."
    return state

def build_research_agent(supabase: Client, groq_api_key: str):
    """Constructs and compiles the LangGraph research agent."""
    graph = StateGraph(ResearchState)

    graph.add_node("retrieve_history", lambda s: retrieve_history(s, supabase))
    graph.add_node("build_summary",    lambda s: build_summary(s, groq_api_key))

    graph.set_entry_point("retrieve_history")
    graph.add_edge("retrieve_history", "build_summary")
    graph.add_edge("build_summary", END)

    return graph.compile()
