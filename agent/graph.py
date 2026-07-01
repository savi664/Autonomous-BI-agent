from langgraph.graph import StateGraph,END,START
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from agent.state import AgentState
from agent.nodes import generate_hypotheses, execute_hypothesis, generate_report,profile_dataset, generate_code 

def should_continue(state: AgentState) -> str:
    hypotheses = state["hypotheses"]
    for hypothesis in hypotheses:
        if hypothesis['status'] == 'open':
            return "generate_code"
    return "generate_report"

def create_graph():
    graph = StateGraph(AgentState)

    graph.add_node("profile_dataset", profile_dataset)
    graph.add_node("generate_hypotheses", generate_hypotheses)
    graph.add_node("generate_code", generate_code)
    graph.add_conditional_edges("execute_hypothesis",should_continue, {
        "generate_code": "generate_code",
        "generate_report": "generate_report"
    })
    graph.add_node("execute_hypothesis", execute_hypothesis)
    graph.add_node("generate_report", generate_report)

    graph.add_edge(START, "profile_dataset")
    graph.add_edge("profile_dataset", "generate_hypotheses")
    graph.add_edge("generate_hypotheses", "generate_code")
    graph.add_edge("generate_code", "execute_hypothesis")
    graph.add_edge("generate_report", END)

    return graph.compile()
