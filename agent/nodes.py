import pandas as pd
from agent.state import AgentState
from langchain_groq import ChatGroq
import os 
import json
from dotenv import load_dotenv
from core.retry import execute_with_retry

load_dotenv()   
os.environ["GROQ_API_KEY"] = os.getenv("GROQ_API_KEY")
llm = ChatGroq(model="llama-3.3-70b-versatile")  

def profile_dataset(state: AgentState) -> dict:
    """
    Profiles the dataset based on the agent's state.

    Args:
        state (AgentState): The current state of the agent.

    Returns:
        dict: A dictionary containing the dataset profile.
    """
    # Load the dataset from the provided code
    try:
        df = state['dataset']
        
        if not isinstance(df, pd.DataFrame):
            raise ValueError("The variable 'df' must be a pandas DataFrame.")
        
        # Profile the dataset
        profile = {"dataset_profile": {
            "num_rows": df.shape[0],
            "num_columns": df.shape[1],
            "column_names": df.columns.tolist(),
            "data_types": df.dtypes.apply(lambda x: x.name).to_dict(),
            "missing_values": df.isnull().sum().to_dict(),
            "unique_values": {col: df[col].nunique() for col in df.columns},
            "summary_statistics": df.describe(include='all').to_dict()
        }}
        
        return profile
    
    except Exception as e:
        return {"error": str(e)}


def generate_hypotheses(state: AgentState) -> list:
    profile = state["dataset_profile"]

    prompt = f"""You are a senior data analyst. Given this dataset profile, generate 5 hypotheses worth investigating.
    
Dataset profile:
{profile}

Return ONLY a JSON array, no explanation, no markdown. Each object must have exactly these keys:
id, question, status, result, code

Example format:
[{{"id": "h1", "question": "...", "status": "open", "result": "", "code": ""}}]"""
    response = llm.invoke(prompt)
    hypotheses = json.loads(response.content)
    return{"hypotheses": hypotheses}

def generate_code(state:AgentState) -> dict:
    hypotheses = state["hypotheses"]
    for hypothesis in hypotheses:
        if hypothesis["status"] == "open":
            prompt = f"""You are a senior data analyst. Given this hypothesis {hypothesis['question']}, generate Python code to test it using the dataset profile {state['dataset_profile']}. Return ONLY a JSON object, no explanation, no markdown. The object must have exactly these keys:
                       code only"""
            response = llm.invoke(prompt)
            content = response.content.strip()
            if content.startswith("```"):
                 lines = content.split("\n")
                 content = "\n".join(lines[1:-1])
            code = json.loads(content.strip())
            hypothesis["code"] = code["code"]
            hypothesis["status"] = "testing"
            break
    return {"hypotheses": hypotheses}   


async def execute_hypothesis(state: AgentState) -> dict:
        hypotheses = state['hypotheses']
        for hypothesis in hypotheses:
            if hypothesis['status'] == 'testing':
                try:
                    result = await execute_with_retry(hypothesis['code'])
                    hypothesis['result'] = result['stdout']   
                    hypothesis['status'] = 'tested'
                    return {"hypotheses": hypotheses, "execution_result": result}
                except Exception as e:
                    hypothesis['result'] = str(e)
                    hypothesis['status'] = 'error'
                break