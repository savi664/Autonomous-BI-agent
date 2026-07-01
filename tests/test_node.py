import asyncio
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agent.nodes import execute_hypothesis, generate_hypotheses
from agent.nodes import generate_code   
async def test_execute_hypothesis():
    fake_state = {
        "dataset": None,
        "dataset_profile": {},
        "hypotheses": [{"id": "h1", "question": "Does revenue vary by region?", "status": "testing", "result": "", "code": "print('F-statistic: 4.23')\nprint('p-value: 0.002')\nprint('Reject null hypothesis.')"}],
        "code": "",
        "report": "",
        "execution_result": {}
    }
    result = await execute_hypothesis(fake_state)
    print("Execution Result:", result)

asyncio.run(test_execute_hypothesis())