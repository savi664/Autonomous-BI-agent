import nbformat as nbf


def export_to_notebook(hypotheses: list, csv_text: str):
    escaped = csv_text.replace("\\", "\\\\").replace('"""', '\\"\\"\\"')
    setup_code = f'''
import pandas as pd
from io import StringIO
csv_data = """{escaped}"""
df = pd.read_csv(StringIO(csv_data))
'''
    # Create a note book object
    nb = nbf.v4.new_notebook()
    cells = []
    cells.append(nbf.v4.new_markdown_cell("InsightFlow Analysis Report"))
    cells.append(nbf.v4.new_code_cell(setup_code))
    for hypothesis in hypotheses:
        cells.append(
            nbf.v4.new_markdown_cell(f"## Hypothesis: {hypothesis['question']}\n")
        )
        cells.append(nbf.v4.new_code_cell(f"{hypothesis['code']}\n"))
        cells.append(
            nbf.v4.new_markdown_cell(f"### Discussion:\n{hypothesis['discussion']}\n")
        )

    nb.cells = cells
    return nb
