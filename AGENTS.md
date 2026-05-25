# AGENTS.md

## Project Overview

This project is an AI Business Insight Copilot built with Streamlit and Python.

The application uploads business datasets, runs local data analysis, and generates markdown business insight reports with help from Gemini.

## Coding Guidelines

- Keep changes small, focused, and easy to review.
- Prefer simple, readable Python code over clever abstractions.
- Follow the existing project structure unless there is a clear reason to introduce a new module.
- Do not remove existing functionality without asking first.
- Do not hardcode API keys, credentials, tokens, or secrets.
- Keep API keys and model configuration in environment variables such as `.env`.

## Report Generation Guidelines

- Keep generated report outputs in markdown.
- Do not invent unsupported business facts in generated reports.
- Base business conclusions on computed analysis results whenever possible.
- When adding business conclusions, clearly separate:
  - Data-backed findings
  - Hypotheses or possible explanations
  - Recommended next steps
- If the data does not support a conclusion, state the limitation instead of guessing.
- Do not send full datasets to the model unless explicitly required; prefer structured summaries, KPIs, trends, risks, and small samples.

## Streamlit App Guidelines

- Keep the UI practical for enterprise users.
- Avoid removing existing pages or workflows unless the user approves.
- Keep analysis and reporting flows understandable:
  - Upload data
  - Run analysis
  - Review insights
  - Generate report

## Testing Guidance

After code changes, suggest testing the app with:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Then open:

```text
http://localhost:8501
```
