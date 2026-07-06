import subprocess
import sys
import asyncio


async def execute_code(code: str, timeout=30) -> dict:
    """
    Executes the code in a subprocess and returns the output or error.
    Uses subprocess.run in a thread pool to avoid Windows event loop
    compatibility issues (SelectorEventLoop vs ProactorEventLoop)
    that cause silent failures inside uvicorn.
    """

    def _run():
        try:
            result = subprocess.run(
                [sys.executable, "-c", code],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if result.returncode == 0:
                return {
                    "status": "success",
                    "stdout": result.stdout.strip(),
                    "stderr": "",
                }
            else:
                return {
                    "status": "error",
                    "stdout": result.stdout.strip(),
                    "stderr": result.stderr.strip(),
                }
        except subprocess.TimeoutExpired:
            return {"status": "error", "stdout": "", "stderr": "Execution timed out."}
        except Exception as e:
            return {
                "status": "error",
                "stdout": "",
                "stderr": f"Subprocess launch failed: {type(e).__name__}: {e}",
            }

    return await asyncio.to_thread(_run)
