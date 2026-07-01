import asyncio
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pandas as pd
from agent.graph import create_graph

async def test_graph():
    graph = create_graph()
    
    # simple fake dataset
    df = pd.DataFrame({
        "date": ["2024-01", "2024-02", "2024-03", "2024-04"],
        "revenue": [5000, 7000, 4500, 8000],
        "customers": [100, 150, 90, 200],
        "region": ["North", "South", "North", "South"],
        "product": ["A", "B", "A", "B"]
    })

    df.to_csv("tests/test_data.csv", index=False)
    
    initial_state = {
        "dataset": df,
        "dataset_path": "tests/test_data.csv",
        "dataset_profile": {},
        "hypotheses": [],
        "code": "",
        "report": "",
        "execution_result": {}
    }
    
    result = await graph.ainvoke(initial_state)
    print("Final Report:\n", result["report"])

asyncio.run(test_graph())