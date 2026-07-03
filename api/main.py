from fastapi import FastAPI, UploadFile, File
from fastapi.staticfiles import StaticFiles
import io
import pandas as pd
import os
import glob
import time
import tempfile
from agent.graph import create_graph

app = FastAPI()
graph = create_graph()


def cleanup_stale_temp_files(max_age_seconds=3600):
    """ Cleans up temporary CSV files older than the specified max_age_seconds in the system's temporary directory."""
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
    for col in df.select_dtypes(include='object').columns:
        cleaned = df[col].astype(str).str.replace(r'[$,%\s]', '', regex=True)
        converted = pd.to_numeric(cleaned, errors='coerce')
        if converted.notna().mean() > 0.9:
            df[col] = converted
    return df

@app.post("/analyze/")
async def analyze_dataset(file: UploadFile = File(...)):
    cleanup_stale_temp_files()

    contents = await file.read()

    fd, content_filepath = tempfile.mkstemp(suffix=".csv")
    try:
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
            "execution_result": {}
        }

        result = await graph.ainvoke(initial_state)
    finally:
        if os.path.exists(content_filepath):
            os.remove(content_filepath)

    return {
        "report": result["report"],
        "hypotheses": [
            {
                "id": h["id"],
                "question": h["question"],
                "result": h["result"],
                "discussion": h["discussion"],
                "code": h["code"],
                "status": h["status"]
            }
            for h in result["hypotheses"]
        ]
    }


frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")