from fastapi import FastAPI ,UploadFile, File
import io
import pandas as pd 
import os
from agent.graph import create_graph
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

graph = create_graph()

@app.post("/analyze/")
async def analyze_dataset(file: UploadFile = File(...)):
    contents = await file.read()
    # Assuming the uploaded file is a CSV, load it into a pandas DataFrame
    df = pd.read_csv(io.StringIO(contents.decode('utf-8')))

    #Save the uploaded file to a temporary location
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

    # invoking the agent graph process
    result = await graph.ainvoke(initial_state)
    os.remove(content_filepath)
    return {"report": result["report"]}
