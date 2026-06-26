import asyncio
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core.classifier import classify_error

result = classify_error("SyntaxError: invalid syntax")
assert result["type"] == "syntax_error"

result = classify_error("NameError: name 'x' is not defined")
assert result["type"] == "name_error"

result = classify_error("TypeError: unsupported operand type(s) for +: 'int' and 'str'")
assert result["type"] == "type_error"

result = classify_error("ImportError: cannot import name 'foo' from 'bar'")
assert result["type"] == "import_error"

result = classify_error("RuntimeError: This is a runtime error")
assert result["type"] == "runtime_error"