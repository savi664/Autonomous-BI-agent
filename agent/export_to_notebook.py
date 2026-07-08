import nbformat as nbf


def export_to_notebook(hypotheses: list, history: list = None, csv_text: str = ""):
    nb = nbf.v4.new_notebook()
    cells = []
    cells.append(nbf.v4.new_markdown_cell("InsightFlow Analysis Report"))
    cells.append(
        nbf.v4.new_code_cell(
            "# TODO: Set your CSV file path here\n"
            'df = pd.read_csv("path/to/your/file.csv")'
        )
    )
    for h in hypotheses:
        cells.append(nbf.v4.new_markdown_cell(f"## Hypothesis: {h['question']}\n"))
        cells.append(nbf.v4.new_code_cell(f"{h['code']}\n"))
        cells.append(nbf.v4.new_markdown_cell(f"### Discussion:\n{h['discussion']}\n"))

    if history:
        cells.append(nbf.v4.new_markdown_cell("## Follow-up Q&A"))
        for entry in history:
            cells.append(nbf.v4.new_markdown_cell(f"**Q:** {entry['question']}"))
            cells.append(nbf.v4.new_markdown_cell(f"**A:** {entry['result']}"))

    nb.cells = cells
    return nb
