from fastapi import FastAPI, UploadFile, File
from fastapi.staticfiles import StaticFiles
import io
import pandas as pd
import os
import glob
import time
import tempfile
from agent.graph import create_graph
from memory.memory_store import create_session, get_session, append_to_session_history
from agent.nodes import answer_follow_up_question

app = FastAPI()
graph = create_graph()


def cleanup_stale_temp_files(max_age_seconds=3600):
    """Cleans up temporary CSV files older than the specified max_age_seconds in the system's temporary directory."""
    temp_dir = tempfile.gettempdir()
    now = time.time()
    for path in glob.glob(os.path.join(temp_dir, "tmp*.csv")):
        try:
            if now - os.path.getmtime(path) > max_age_seconds:
                os.remove(path)
        except OSError:
            pass


def auto_convert_numeric_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Attempts to convert object-dtype columns to numeric if the values
    are actually numeric but stored as strings
    """
    for col in df.select_dtypes(include="object").columns:
        cleaned = df[col].astype(str).str.replace(r"[$,%\s]", "", regex=True)
        converted = pd.to_numeric(cleaned, errors="coerce")
        if converted.notna().mean() > 0.9:
            df[col] = converted
    return df


@app.post("/analyze/")
async def analyze_dataset(file: UploadFile = File(...)):
    cleanup_stale_temp_files()

    contents = await file.read()

    fd, content_filepath = tempfile.mkstemp(suffix=".csv")
    with os.fdopen(fd, "wb") as f:
        f.write(contents)

    df = pd.read_csv(content_filepath)
    df = auto_convert_numeric_columns(df)
    df.to_csv(content_filepath, index=False)

    initial_state = {
        "dataset": df,
        "dataset_path": content_filepath,
        "dataset_profile": {},
        "hypotheses": [],
        "code": "",
        "report": "",
        "discussion": "",
        "execution_result": {},
    }

    result = await graph.ainvoke(initial_state)
    session_id = create_session(df, result["dataset_profile"], content_filepath)

    return {
        "session_id": session_id,
        "report": result["report"],
        "hypotheses": [
            {
                "id": h["id"],
                "question": h["question"],
                "result": h["result"],
                "discussion": h["discussion"],
                "code": h["code"],
                "status": h["status"],
            }
            for h in result["hypotheses"]
        ],
    }


@app.post("/followup/")
async def followup(session_id: str, question: str):
    session = get_session(session_id)
    if not session:
        return {"error": "Session not found or expired."}
    else:
        outcome = await answer_follow_up_question(
            question=question,
            dataset_profile=session["dataset_profile"],
            dataset_path=session["dataset_path"],
            history=session["history"],
        )
        append_to_session_history(session_id, question, outcome.get("result", ""))
        return outcome


frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
