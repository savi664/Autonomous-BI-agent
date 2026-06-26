import subprocess
import sys
import asyncio

async def execute_code(code:str,timeout=10) -> dict:
    """
    Executes the code and return the output or and error if it occurs

    """
    try:
        result = await asyncio.create_subprocess_exec(
             sys.executable, "-c", code,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout,stderr = await asyncio.wait_for(result.communicate(), timeout=timeout)
        
        if result.returncode == 0:
            return {"status": "success", "stdout": stdout.decode('utf-8').strip(), "stderr": ""}
        else:
            return {"status": "error", "stdout": stdout.decode('utf-8').strip(), "stderr": stderr.decode('utf-8').strip()}
    except asyncio.TimeoutError:
        result.kill()
        await result.communicate()
        return {"status": "error", "stdout": "", "stderr": "Execution timed out."}
