import nbformat as nbf


def export_to_notebook(hypotheses: list, csv_text: str = ""):
    nb = nbf.v4.new_notebook()
    cells = []
    cells.append(nbf.v4.new_markdown_cell("InsightFlow Analysis Report"))
    cells.append(
        nbf.v4.new_code_cell(
            "# TODO: Set your CSV file path here\n"
            'df = pd.read_csv("path/to/your/file.csv")'
        )
    )
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
