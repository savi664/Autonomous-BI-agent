import pandas as pd
from agent.state import AgentState
from langchain_openai import ChatOpenAI
import os 
import json
from dotenv import load_dotenv
from core.retry import execute_with_retry

load_dotenv()   
os.environ["GITHUB_TOKEN"] = os.getenv("GITHUB_TOKEN")

llm = ChatOpenAI(
    model="openai/gpt-5",
    api_key=os.getenv("GITHUB_TOKEN"),
    base_url="https://models.github.ai/inference",
)

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
            "summary_statistics": df.describe(include='all').to_dict(),
            "sample_data": df.head().to_dict(orient='records'),
            "correlation_matrix": df.select_dtypes(include='number').corr().to_dict()
        }}
        
        return profile
    
    except Exception as e:
        return {"error": str(e)}


def generate_hypotheses(state: AgentState) -> dict:
    profile = state["dataset_profile"]

    prompt = f"""You are a senior data analyst tasked with investigating a business dataset.

Dataset profile:
{profile}

Generate exactly 5 hypotheses about the BUSINESS METRICS in this dataset. Focus only on relationships between the actual columns: {profile.get('column_names', [])}.

Rules:
- Hypotheses must be about business insights, not about the dataset structure itself
- Each hypothesis must be testable with pandas and scipy using a DataFrame called 'df' that already exists in memory
- Do NOT import data or read any files — df is already loaded
- Use only: pandas, scipy, numpy

Return ONLY a JSON array, no explanation, no markdown, no code blocks.
Each object must have exactly these keys: id, question, status, result, code

Example format:
[{{"id": "h1", "question": "Is there a correlation between revenue and customers?", "status": "open", "result": "", "code": ""}}]"""
    response = llm.invoke(prompt)
    content = response.content.strip()

    if "```" in content:
        lines = content.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        content = "\n".join(lines)

    try:
        hypotheses = json.loads(content.strip(), strict=False)
    except json.JSONDecodeError as e:
        print(f"Failed to parse hypotheses JSON: {e}")
        print(f"Raw content: {content}")
        raise
    return {"hypotheses": hypotheses}

def generate_code(state: AgentState) -> dict:
    hypotheses = state["hypotheses"]
    for hypothesis in hypotheses:
        if hypothesis["status"] == "open":
            prompt = f"""You are a senior data analyst. Generate Python code to test this hypothesis:

Hypothesis: {hypothesis['question']}

The DataFrame is already loaded as 'df' with these exact columns: {state['dataset_profile']['column_names']}

Rules:
- Only use columns that exist in the list above
- df is already loaded, do NOT read any files
- Use only pandas, scipy, numpy
- Print the results

Return ONLY a JSON object with one key: "code"
The value must be a valid Python code string.
No markdown, no explanation."""
            
            response = llm.invoke(prompt)
            content = response.content.strip()
            
            if "```" in content:
                lines = content.split("\n")
                lines = [l for l in lines if not l.strip().startswith("```")]
                content = "\n".join(lines)
            
            try:
                 code = json.loads(content.strip(), strict=False)
                 hypothesis["code"] = code["code"]
                 hypothesis["status"] = "testing"
            except json.JSONDecodeError:
                 hypothesis["status"] = "error"
                 hypothesis["result"] = "Failed to generate valid code"
            break
    return {"hypotheses": hypotheses}


async def execute_hypothesis(state: AgentState) -> dict:
    hypotheses = state['hypotheses']
    for hypothesis in hypotheses:
        if hypothesis['status'] == 'testing':
            try:
                csv_load = f'import pandas as pd\ndf = pd.read_csv(r"{state["dataset_path"]}")\n'
                full_code = csv_load + hypothesis["code"]
                result = await execute_with_retry(full_code)
                hypothesis['result'] = result['stdout'].strip()
                hypothesis['status'] = 'tested'
                return {"hypotheses": hypotheses, "execution_result": result}
            except Exception as e:
                hypothesis['result'] = str(e)
                hypothesis['status'] = 'error'
            break
    return {"hypotheses": hypotheses}

def generate_report(state: AgentState) -> dict:
    hypotheses = state['hypotheses']
    tested_hypotheses = [h for h in hypotheses if h['status'] == 'tested']
    findings = "\n".join([f"Hypothesis {h['id']}: {h['question']}\nResult: {h['result']}" for h in tested_hypotheses])

    prompt = f"""
    You are a senior data analyst. Given these findings:

    {findings}

    Write a structured business report with:
    1. Executive summary (3-5 bullet points, non-technical)
    2. Key findings with evidence
    3. Recommended next actions

    Return plain text, no JSON, no markdown.
    """
    response = llm.invoke(prompt)
        
    return {"report": response.content.strip()}
