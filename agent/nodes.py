import asyncio
import pandas as pd
from agent.state import AgentState
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
import re
import os
import json
from dotenv import load_dotenv
from core.retry import execute_with_retry

load_dotenv()

primary_llm = ChatGoogleGenerativeAI(
    model="gemini-3.1-flash-lite", google_api_key=os.getenv("GOOGLE_API_KEY")
)

fallback_llm = ChatOpenAI(
    model="devstral-small-2:24b",
    api_key=os.getenv("LLM7_IO_TOKEN"),
    base_url="https://api.llm7.io/v1",
)


def invoke_llm(prompt: str):
    try:
        response = primary_llm.invoke(prompt)
    except Exception as e:
        print(f"Primary LLM failed ({e}). Falling back to llm7.")
        response = fallback_llm.invoke(prompt)
    if isinstance(response.content, list):
        response.content = "".join(
            p.get("text", str(p)) for p in response.content if isinstance(p, dict)
        )
    return response


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
    try:
        df = state["dataset"]

        if not isinstance(df, pd.DataFrame):
            raise ValueError("The variable 'df' must be a pandas DataFrame.")

        profile = {
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

        validation = extract_json(
            invoke_llm(
                f"""You are a data validator. Dataset columns: {profile["column_names"]}
Sample rows: {profile["sample_data"]}

Is this dataset related to BUSINESS metrics (sales, customers, churn, revenue, finance, HR, operations, marketing, etc.)?
Return ONLY JSON: {{"is_business": true/false, "reason": "explanation if false"}}"""
            ).content.strip()
        )

        if not validation.get("is_business", True):
            return {
                "dataset_profile": {
                    "validation_error": validation.get(
                        "reason", "Not business-related."
                    )
                }
            }

        return {"dataset_profile": profile}

    except Exception as e:
        return {"error": str(e)}


def generate_hypotheses(state: AgentState) -> dict:
    profile = state["dataset_profile"]

    if "validation_error" in profile:
        return {
            "hypotheses": [
                {
                    "id": "error",
                    "question": profile["validation_error"],
                    "status": "error",
                    "result": profile["validation_error"],
                    "code": "",
                    "type": "text",
                }
            ]
        }

    prompt = f"""You are a senior data analyst tasked with investigating a business dataset.

Dataset profile:
{profile}

Generate 7 hypotheses about the BUSINESS METRICS in this dataset. Focus only on relationships between the actual columns: {profile.get("column_names", [])}.

- Hypotheses h1 through h5 must be text-based statistical tests (NO charts allowed).
- Hypotheses h6 and h7 must be visualization hypotheses that require a chart (e.g. "What does the distribution of MonthlyCharges look like?", "How does churn vary across contract types?").

Rules:
- Hypotheses must be about business insights, not about the dataset structure itself
- Each hypothesis must be testable with pandas, scipy, numpy, matplotlib, seaborn using a DataFrame called 'df' that already exists in memory
- Do NOT import data or read any files — df is already loaded
- Use only: pandas, scipy, numpy, matplotlib, seaborn

Return ONLY a JSON array, no explanation, no markdown, no code blocks.
Each object must have exactly these keys: id, question, status, result, code, type

- For h1-h5, "type" must be "text"
- For h6-h7, "type" must be "visualization"

Example format:
[{{"id": "h1", "question": "Is there a correlation between revenue and customers?", "status": "open", "result": "","discussion":"","code": "", "type": "text"}}]"""
    response = invoke_llm(prompt)
    content = response.content.strip()

    try:
        hypotheses = extract_json(content)
    except Exception as e:
        print(f"Failed to parse hypotheses JSON: {e}")
        print(f"Raw content: {content}")
        raise
    return {"hypotheses": hypotheses}


async def generate_code(state: AgentState) -> dict:
    hypotheses = state["hypotheses"]
    sem = asyncio.Semaphore(3)

    async def process_hypothesis(h):
        chart_rule = (
            "Do NOT generate any charts or images. Only print text output (numbers, statistics, conclusions)."
            if h.get("type") == "text"
            else 'You MUST generate a chart using matplotlib/seaborn. Save the figure to a BytesIO buffer, encode it as base64, and print it EXACTLY like this: print(f"###IMG###{base64_string}###IMG###"). Also print a brief text explanation BEFORE the image line explaining what the chart shows.'
        )
        prompt = f"""You are a senior data analyst. Generate Python code to test this hypothesis:

Hypothesis: {h["question"]}

The DataFrame is already loaded as 'df' with these exact columns: {state["dataset_profile"]["column_names"]} and these data types: {state["dataset_profile"]["data_types"]}.

Rules:
- Only use columns that exist in the list above
- df is already loaded, do NOT read any files
- Use only: pandas, scipy, numpy, matplotlib, seaborn
- Print the results clearly
- If a column has an 'object' data type but you need it for numeric analysis, ALWAYS use pd.to_numeric(df[column], errors='coerce') before processing.
- {chart_rule}

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
            async with sem:
                response = await asyncio.to_thread(invoke_llm, prompt)
            content = response.content.strip()
            try:
                code_obj = extract_json(content)
                h["code"] = code_obj["code"]
                h["status"] = "testing"
                return
            except Exception:
                if i == 0:
                    prompt += "\n\nYour response was not valid JSON. Return ONLY a JSON object with one key: 'code'."
                else:
                    h["status"] = "error"
                    h["result"] = "Failed to generate valid code"

    open_hypotheses = [h for h in hypotheses if h["status"] == "open"]
    if open_hypotheses:
        await asyncio.gather(*[process_hypothesis(h) for h in open_hypotheses])

    return {"hypotheses": hypotheses}


async def execute_hypothesis(state: AgentState) -> dict:
    hypotheses = state["hypotheses"]
    sem = asyncio.Semaphore(3)

    async def process_hypothesis(h):
        try:
            csv_load = f'import pandas as pd\ndf = pd.read_csv(r"{state["dataset_path"]}")\ndf = df.dropna()\n'
            for attempt in range(2):
                full_code = csv_load + h["code"]
                result = await execute_with_retry(full_code)
                if result.get("status") == "success":
                    output = result["stdout"].strip()
                    if h.get("type") == "text":
                        output = re.sub(
                            r"###IMG###.+?###IMG###", "", output, flags=re.DOTALL
                        ).strip()
                    h["result"] = output
                    h["status"] = "tested"
                    return
                elif attempt == 1:
                    error_msg = result.get("stderr", "Unknown error")
                    h["result"] = f"Error: {error_msg}"
                    h["status"] = "error"
                else:
                    error_msg = result.get("stderr", "Unknown error")
                    prompt = f"""This code failed with this error:

                            {h["code"]}

                            Error:
                            {error_msg}

                            Fix the code. Return ONLY a JSON object with one key: 'code'"""
                    try:
                        async with sem:
                            llm_response = await asyncio.to_thread(invoke_llm, prompt)
                        h["code"] = extract_json(llm_response.content.strip())["code"]
                    except Exception:
                        h["result"] = f"Error: {error_msg}."
                        h["status"] = "error"
                        return
        except Exception as e:
            h["result"] = str(e)
            h["status"] = "error"

    testing_hypotheses = [h for h in hypotheses if h["status"] == "testing"]
    if testing_hypotheses:
        await asyncio.gather(*[process_hypothesis(h) for h in testing_hypotheses])

    return {"hypotheses": hypotheses}


def discuss_output(state: AgentState) -> dict:
    hypotheses = state["hypotheses"]
    tested_hypotheses = [h for h in hypotheses if h["status"] == "tested"]
    findings = "\n".join(
        [
            f"Hypothesis {h['id']}: {h['question']}\nResult: {re.sub(r'###IMG###.+?###IMG###', '[CHART IMAGE]', h['result'])}"
            for h in tested_hypotheses
        ]
    )

    prompt = f"""You are a senior data analyst. Given these findings:

    {findings}

    For EACH hypothesis, write a short 2-3 sentence plain-English discussion explaining what the result means for the business — no jargon, no p-value talk, just what it means practically.

    Return ONLY a JSON object mapping hypothesis id to discussion text, like:
    {{"h1": "Customers who stay longer tend to pay more per month, which suggests...", "h2": "..."}}

    No markdown, no explanation, just the JSON object."""

    response = invoke_llm(prompt)
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
            f"Hypothesis {h['id']}: {h['question']}\nResult: {re.sub(r'###IMG###.+?###IMG###', '[CHART IMAGE]', h['result'])}"
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
    response = invoke_llm(prompt)

    return {"report": response.content.strip()}


async def answer_follow_up_question(
    question: str, dataset_profile: dict, dataset_path: str, history
) -> dict:
    history_context = "\n".join(
        [
            f"Q: {h['question']}\nA: {re.sub(r'###IMG###.+?###IMG###', '[CHART IMAGE]', h['result'])}"
            for h in history[-3:]
        ]
    )

    base_prompt = f"""You are a senior data analyst. The DataFrame is already loaded as 'df' with these columns and types: {dataset_profile["data_types"]}

Previous questions in this session:
{history_context if history_context else "(none yet)"}

New question: {question}

IMPORTANT: You MUST ALWAYS return valid JSON with a "code" key — no exceptions.
If the question is vague or lacks context, interpret it yourself, scope it down, and write code to investigate something relevant.
Never refuse or ask for clarification. Never respond with natural language.

Generate Python code using pandas, scipy, numpy, matplotlib, seaborn.

Only generate a chart if the user explicitly asks for a visualization (e.g. "show me a chart", "plot", "visualize"). Otherwise, use only text/statistical output. If you do generate a chart, print a brief text explanation BEFORE the image line explaining what the chart shows.

If the question cannot be answered with a chart or statistical analysis, print a clear message explaining why.

CRITICAL — NaN handling:
Before every statistical test, use this exact pattern:
  subset = df[['column1', 'column2']].dropna()
  # then run your test on subset['column1'] and subset['column2']
Check that len(subset) >= 2 before running the test. If len(subset) < 2, print "Insufficient data for this test" instead.

Print the results clearly.

Return ONLY a JSON object with one key: "code"
No markdown, no explanation."""

    csv_load = (
        f'import pandas as pd\ndf = pd.read_csv(r"{dataset_path}")\ndf = df.dropna()\n'
    )
    last_error = ""

    for attempt in range(3):
        prompt = base_prompt
        if attempt > 0:
            prompt += f"\n\nThe previous attempt failed: {last_error}. Return ONLY valid JSON with a 'code' key."

        try:
            response = await asyncio.to_thread(invoke_llm, prompt)
            content = response.content.strip()
        except Exception as e:
            last_error = f"LLM call failed: {e}"
            if attempt == 2:
                return {"status": "error", "result": f"LLM call failed: {e}"}
            continue

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
                if "###IMG###" in stdout:
                    text_part = stdout.split("###IMG###")[0].strip()
                    if text_part:
                        summary_prompt = f"""The user asked: "{question}"

The generated code produced this text output (before a chart):
{text_part}

Summarize the answer in 2-3 clear, conversational sentences. Focus on the key insight."""
                        summary = await asyncio.to_thread(invoke_llm, summary_prompt)
                        chart_part = stdout[stdout.index("###IMG###") :]
                        return {
                            "status": "tested",
                            "result": summary.content.strip() + "\n\n" + chart_part,
                            "code": code,
                        }
                    return {"status": "tested", "result": stdout, "code": code}
                summary_prompt = f"""The user asked: "{question}"

The generated code produced this output:
{stdout}

Summarize the answer in 2-3 clear, conversational sentences. Focus on the key insight. Do not repeat raw numbers unless they are the main finding."""
                summary = await asyncio.to_thread(invoke_llm, summary_prompt)
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
