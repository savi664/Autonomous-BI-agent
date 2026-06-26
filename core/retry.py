from core.executor import execute_code
from core.classifier import classify_error

async def execute_with_retry(code:str, max_retries=3):
    """
    Executes a function with retry logic.

    """
    last_error_info = None
    for attempt in range(max_retries):
        result = await execute_code(code)
        if result["status"] == "success":
            return {"status": "success", "stdout": result["stdout"], "stderr": "","attempts":attempt+1}
        else:
            last_error_info = classify_error(result["stderr"])
            if last_error_info["type"] == "syntax_error":
                print(f"Attempt {attempt + 1} failed with error: {last_error_info['type']} - {last_error_info['message']}")
                break  
            print(f"Attempt {attempt + 1} failed with error: {last_error_info['type']} - {last_error_info['message']}")
    return {"status": "error", "stdout": "", "stderr": last_error_info["message"] ,"attempts":max_retries}