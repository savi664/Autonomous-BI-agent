from core.executor import execute_code
from core.classifier import classify_error

async def execute_with_retry(code: str, max_retries=3):
    """
    Executes code with retry logic. Returns a result dict with
    status, stdout, stderr, and attempts count.
    """
    last_error_info = None
    for attempt in range(max_retries):
        try:
            result = await execute_code(code)
        except Exception as e:
            # Guard against unexpected exceptions from execute_code
            result = {"status": "error", "stdout": "", "stderr": f"{type(e).__name__}: {e}"}

        if result["status"] == "success":
            return {"status": "success", "stdout": result["stdout"], "stderr": "", "attempts": attempt + 1}
        else:
            stderr_text = result.get("stderr", "") or ""
            if not stderr_text.strip():
                stderr_text = "(no error output captured)"
            last_error_info = classify_error(stderr_text)
            print(f"Attempt {attempt + 1} failed with error: {last_error_info['type']} - {last_error_info['message']}")
            if last_error_info["type"] == "syntax_error":
                break

    error_message = last_error_info["message"] if last_error_info else "(unknown failure — no error info)"
    return {"status": "error", "stdout": "", "stderr": error_message, "attempts": max_retries}