def classify_error(stderr:str) -> dict:

    last_line = stderr.strip().split("\n")[-1]

    if "SyntaxError" in stderr:
        return {"type": "syntax_error", "message": last_line}
    elif "NameError" in stderr:
        return {"type": "name_error", "message": last_line}
    elif "TypeError" in stderr:
        return {"type": "type_error", "message": last_line}
    elif "ImportError" in stderr:
        return {"type": "import_error", "message": last_line}
    elif "RuntimeError" in stderr:
        return {"type": "runtime_error", "message": last_line}
    elif "Execution timed out" in stderr:
        return {"type": "timeout_error", "message": last_line} 
    else:
        return {"type": "unknown_error", "message": last_line}