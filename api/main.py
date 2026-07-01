from fastapi import FastAPI, UploadFile, File
from fastapi.staticfiles import StaticFiles
import io
import pandas as pd
import os
from agent.graph import create_graph

app = FastAPI()

graph = create_graph()

@app.post("/analyze/")
async def analyze_dataset(file: UploadFile = File(...)):
    contents = await file.read()
    df = pd.read_csv(io.StringIO(contents.decode('utf-8')))

    content_filepath = f"temp_{file.filename}"
    with open(content_filepath, "wb") as f:
        f.write(contents)

    initial_state = {
        "dataset": df,
        "dataset_path": content_filepath,
        "dataset_profile": {},
        "hypotheses": [],
        "code": "",
        "report": "",
        "execution_result": {}
    }

    try:
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
                "code": h["code"],
                "status": h["status"]
            }
            for h in result["hypotheses"]
        ]
    }

frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")