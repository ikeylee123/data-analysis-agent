# Offline Evaluation

Run the three-domain deterministic evaluation from the repository root:

```powershell
.\.venv\Scripts\python.exe -m evals.run_eval
```

The runner does not instantiate or call an LLM client. It uses the committed Retail, SaaS, and Logistics fixtures to check exact KPI values, local report structure, deterministic fallback, and separation of evidence, hypotheses, and actions. It exits with a non-zero status if any check fails.