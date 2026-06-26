import asyncio 
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core.executor import execute_code



results = asyncio.run(execute_code("print('Hello, World!')"))
assert results["status"] == "success"
assert results["stdout"] == "Hello, World!" 

results = asyncio.run(execute_code("print(1/0)"))
assert results["status"] == "error"
assert "ZeroDivisionError" in results["stderr"]


results = asyncio.run(execute_code("import pytorch"))
assert results["status"] == "error"
assert "ModuleNotFoundError" in results["stderr"]


result = asyncio.run(execute_code("while True: pass", timeout=1))   
assert result["status"] == "error"
assert "Execution timed out" in result["stderr"]

result = asyncio.run(execute_code("x = 1 + 1"))
assert result["status"] == "success"
assert result["stdout"] == ""