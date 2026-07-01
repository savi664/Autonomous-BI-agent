import asyncio
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from agent.nodes import generate_report
async def test_generate_report():
    fake_state = {
        "dataset": None,
        "dataset_profile": {},
        "hypotheses": [
            {
                "id": "h1",
                "question": "Does revenue vary significantly across regions?",
                "status": "tested",
                "result": "F-statistic: 4.23\np-value: 0.002\nReject null hypothesis. Revenue varies significantly across regions.",
                "code": ""
            },
            {
                "id": "h2",
                "question": "Is there a correlation between customers and revenue?",
                "status": "tested",
                "result": "Correlation coefficient: 0.87\np-value: 0.001\nStrong positive correlation between customers and revenue.",
                "code": ""
            }
        ],
        "code": "",
        "report": "",
        "execution_result": {}
    }
    result = generate_report(fake_state)
    print("Report:\n", result["report"])

asyncio.run(test_generate_report())