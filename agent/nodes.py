import pandas as pd
from agent.state import AgentState
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI
from groq import RateLimitError
import re
import os
import json
from dotenv import load_dotenv
from core.retry import execute_with_retry

load_dotenv()
os.environ["LLM7_IO_TOKEN"] = os.getenv("LLM7_IO_TOKEN")

primary_llm = ChatGroq(model="llama-3.3-70b-versatile")

fallback_llm = ChatOpenAI(
    model_name="devstral-small-2:24b",
    api_key=os.getenv("LLM7_IO_TOKEN"),
    base_url="https://api.llm7.io/v1",
)


def invoke_with_fallback(prompt: str):
    try:
        return primary_llm.invoke(prompt)
    except RateLimitError:
        print("Primary LLM rate limit exceeded. Falling back to secondary LLM.")
        return fallback_llm.invoke(prompt)


def extract_json(text: str):
    """Robustly extracts and parses JSON from a string that may contain surrounding text."""
    try:
        return json.loads(text.strip(), strict=False)
    except json.JSONDecodeError:
        match = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1).strip(), strict=False)
            except json.JSONDecodeError:
                pass
        clean_text = re.sub(r"```[a-z]*\n?", "", text, flags=re.IGNORECASE).strip()
        clean_text = clean_text.strip("```")
        return json.loads(clean_text, strict=False)


def profile_dataset(state: AgentState) -> dict:
    """
    provide the LLM with the profiles of the database
    """
    # Load the dataset from the provided code
    try:
        df = state["dataset"]

        if not isinstance(df, pd.DataFrame):
            raise ValueError("The variable 'df' must be a pandas DataFrame.")

        # Profile the dataset
        profile = {
            "dataset_profile": {
                "num_rows": df.shape[0],
                "num_columns": df.shape[1],
                "column_names": df.columns.tolist(),
                "data_types": df.dtypes.apply(lambda x: x.name).to_dict(),
                "missing_values": df.isnull().sum().to_dict(),
                "unique_values": {col: df[col].nunique() for col in df.columns},
                "summary_statistics": df.describe(include="all").to_dict(),
                "sample_data": df.head().to_dict(orient="records"),
                "correlation_matrix": df.select_dtypes(include="number").corr().to_dict(),
            }
        }

        return profile

    except Exception as e:
        return {"error": str(e)}


def generate_hypotheses(state: AgentState) -> dict:
    profile = state["dataset_profile"]

    prompt = f"""You are a senior data analyst tasked with investigating a business dataset.

Dataset profile:
{profile}

Generate exactly 5 hypotheses about the BUSINESS METRICS in this dataset. Focus only on relationships between the actual columns: {profile.get("column_names", [])}.

Rules:
- Hypotheses must be about business insights, not about the dataset structure itself
- Each hypothesis must be testable with pandas and scipy using a DataFrame called 'df' that already exists in memory
- Do NOT import data or read any files — df is already loaded
- Use only: pandas, scipy, numpy

Return ONLY a JSON array, no explanation, no markdown, no code blocks.
Each object must have exactly these keys: id, question, status, result, code

Example format:
[{{"id": "h1", "question": "Is there a correlation between revenue and customers?", "status": "open", "result": "","discussion":"","code": ""}}]"""
    response = invoke_with_fallback(prompt)
    content = response.content.strip()

    try:
        hypotheses = extract_json(content)
    except Exception as e:
        print(f"Failed to parse hypotheses JSON: {e}")
        print(f"Raw content: {content}")
        raise
    return {"hypotheses": hypotheses}


def generate_code(state: AgentState) -> dict:
    hypotheses = state["hypotheses"]
    for hypothesis in hypotheses:
        if hypothesis["status"] == "open":
            prompt = f"""You are a senior data analyst. Generate Python code to test this hypothesis:

Hypothesis: {hypothesis["question"]}

The DataFrame is already loaded as 'df' with these exact columns: {state["dataset_profile"]["column_names"]} and these data types: {state["dataset_profile"]["data_types"]}.

Rules:
- Only use columns that exist in the list above
- df is already loaded, do NOT read any files
- Use only pandas, scipy, numpy
- Print the results clearly
- If a column has an 'object' data type but you need it for numeric analysis, ALWAYS use pd.to_numeric(df[column], errors='coerce') before processing.

CRITICAL — NaN handling:
Before every statistical test, use this exact pattern:
  subset = df[['column1', 'column2']].dropna()
  # then run your test on subset['column1'] and subset['column2']
Check that len(subset) >= 2 before running the test. If len(subset) < 2, print "Insufficient data for this test" instead.
If the test involves groups (e.g. t-test, ANOVA), also check each group has >= 2 rows after dropping NaN.

For categorical columns used as group labels, do NOT dropna() on them — only the numeric columns used in the test.

Return ONLY a JSON object with one key: "code"
The value must be a valid Python code string.
No markdown, no explanation."""
        for i in range(2):
            response = invoke_with_fallback(prompt)
            content = response.content.strip()
            try:
                code_obj = extract_json(content)
                hypothesis["code"] = code_obj["code"]
                hypothesis["status"] = "testing"
                break
            except Exception:
                if i == 0:
                    prompt += "\n\nYour response was not valid JSON. Return ONLY a JSON object with one key: 'code'."
                else:
                    hypothesis["status"] = "error"
                    hypothesis["result"] = "Failed to generate valid code"
    return {"hypotheses": hypotheses}


async def execute_hypothesis(state: AgentState) -> dict:
    hypotheses = state["hypotheses"]
    for hypothesis in hypotheses:
        if hypothesis["status"] == "testing":
            try:
                csv_load = f'import pandas as pd\ndf = pd.read_csv(r"{state["dataset_path"]}")\ndf = df.dropna()\n'
                
                for attempt in range(2):
                    full_code = csv_load + hypothesis["code"]
                    result = await execute_with_retry(full_code)

                    if result.get("status") == "success":
                        hypothesis["result"] = result["stdout"].strip()
                        hypothesis["status"] = "tested"
                    elif attempt == 1:
                        error_msg = result.get("stderr", "Unknown error")
                        hypothesis["result"] = f"Error: {error_msg}"
                        hypothesis["status"] = "error"
                    else:
                        error_msg = result.get("stderr", "Unknown error")
                        prompt=f"""This code failed with this error:

                            {hypothesis['code']}

                            Error:
                            {error_msg}

                            Fix the code. Return ONLY a JSON object with one key: 'code'"""
                        try:
                            hypothesis["code"] = extract_json(invoke_with_fallback(prompt).content.strip())["code"]
                        except Exception:
                            hypothesis["result"] = f"Error: {error_msg}."
                            hypothesis["status"] = "error"
                            break
            except Exception as e:
                hypothesis["result"] = str(e)
                hypothesis["status"] = "error"
    return {"hypotheses": hypotheses}


def discuss_output(state: AgentState) -> dict:
    hypotheses = state["hypotheses"]
    tested_hypotheses = [h for h in hypotheses if h["status"] == "tested"]
    findings = "\n".join(
        [
            f"Hypothesis {h['id']}: {h['question']}\nResult: {h['result']}"
            for h in tested_hypotheses
        ]
    )

    prompt = f"""You are a senior data analyst. Given these findings:

    {findings}

    For EACH hypothesis, write a short 2-3 sentence plain-English discussion explaining what the result means for the business — no jargon, no p-value talk, just what it means practically.

    Return ONLY a JSON object mapping hypothesis id to discussion text, like:
    {{"h1": "Customers who stay longer tend to pay more per month, which suggests...", "h2": "..."}}

    No markdown, no explanation, just the JSON object."""

    response = invoke_with_fallback(prompt)
    content = response.content.strip()

    try:
        discussions = extract_json(content)
    except Exception:
        discussions = {}

    for hypothesis in hypotheses:
        hypothesis["discussion"] = discussions.get(hypothesis["id"], "")

    return {"hypotheses": hypotheses}


def generate_report(state: AgentState) -> dict:
    hypotheses = state["hypotheses"]
    tested_hypotheses = [h for h in hypotheses if h["status"] == "tested"]
    findings = "\n".join(
        [
            f"Hypothesis {h['id']}: {h['question']}\nResult: {h['result']}"
            for h in tested_hypotheses
        ]
    )

    prompt = f"""
    You are a senior data analyst. Given these findings:

    {findings}

    Write a structured business report with:
    1. Executive summary (3-5 bullet points, non-technical)
    2. Key findings with evidence
    3. Recommended next actions

    Return plain text, no JSON, no markdown.
    """
    response = invoke_with_fallback(prompt)

    return {"report": response.content.strip()}


async def answer_follow_up_question(
    question: str, dataset_profile: dict, dataset_path: str, history
) -> dict:
    history_context = "\n".join(
        [f"Q: {h['question']}\nA: {h['result']}" for h in history[-3:]]
    )

    base_prompt = f"""You are a senior data analyst. The DataFrame is already loaded as 'df' with these columns and types: {dataset_profile["data_types"]}

Previous questions in this session:
{history_context if history_context else "(none yet)"}

New question: {question}

IMPORTANT: You MUST ALWAYS return valid JSON with a "code" key — no exceptions.
If the question is vague or lacks context, interpret it yourself, scope it down, and write code to investigate something relevant.
Never refuse or ask for clarification. Never respond with natural language.

Generate Python code using pandas, scipy, numpy.

CRITICAL — NaN handling:
Before every statistical test, use this exact pattern:
  subset = df[['column1', 'column2']].dropna()
  # then run your test on subset['column1'] and subset['column2']
Check that len(subset) >= 2 before running the test. If len(subset) < 2, print "Insufficient data for this test" instead.

Print the results clearly.

Return ONLY a JSON object with one key: "code"
No markdown, no explanation."""

    csv_load = f'import pandas as pd\ndf = pd.read_csv(r"{dataset_path}")\n'
    last_error = ""

    for attempt in range(3):
        prompt = base_prompt
        if attempt > 0:
            prompt += f"\n\nThe previous attempt failed: {last_error}. Return ONLY valid JSON with a 'code' key."

        response = invoke_with_fallback(prompt)
        content = response.content.strip()

        try:
            code_obj = extract_json(content)
            code = code_obj["code"]
        except Exception:
            last_error = "Response was not valid JSON with a 'code' key"
            if attempt == 2:
                return {
                    "status": "error",
                    "result": "Failed to generate valid code for this question.",
                }
            continue

        try:
            full_code = csv_load + code
            result = await execute_with_retry(full_code)
            if result.get("status") == "success":
                stdout = result.get("stdout", "").strip()
                summary_prompt = f"""The user asked: "{question}"

The generated code produced this output:
{stdout}

Summarize the answer in 2-3 clear, conversational sentences. Focus on the key insight. Do not repeat raw numbers unless they are the main finding."""
                summary = invoke_with_fallback(summary_prompt)
                return {
                    "status": "tested",
                    "result": summary.content.strip(),
                    "code": code,
                }
            else:
                last_error = result.get("stderr", "Unknown error")
                if attempt == 2:
                    return {
                        "status": "error",
                        "result": f"Error: {last_error}",
                    }
        except Exception as e:
            last_error = str(e)
            if attempt == 2:
                return {"status": "error", "result": str(e)}

    return {"status": "error", "result": "Failed after multiple attempts."}
