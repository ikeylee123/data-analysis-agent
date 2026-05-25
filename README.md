# AI Business Insight Copilot

AI Business Insight Copilot is a Streamlit-based business analytics assistant that helps turn uploaded datasets into structured business insights, risk signals, and management-style markdown reports.

The project is designed as a GitHub portfolio project for demonstrating practical AI-assisted data analysis workflows across multiple business domains. It supports report generation in both Chinese and English.

## 1. Project Overview

This application helps users upload business datasets, run automated analysis, identify key metrics and risks, and generate a structured business insight report.

The current focus is on realistic enterprise reporting rather than simple data summaries. Generated reports are designed to answer:

- What happened?
- Why does it matter?
- What evidence supports the finding?
- What should the business do next?
- What limitations prevent stronger conclusions?

## 2. Key Features

- Upload CSV, Excel, or PDF files.
- Automatically identify common business fields such as sales, profit, discount, quantity, region, category, product, customer, date, and order fields.
- Generate KPI summaries and derived business metrics.
- Detect loss-making records, high-discount loss records, numeric outliers, and missing-field risks.
- Produce segment deep dives for business dimensions such as region, category, product, customer, and segment.
- Generate markdown business reports with evidence, confidence levels, hypotheses, recommendations, and data limitations.
- Support Chinese and English report generation.
- Include multi-industry sample datasets and sample reports for portfolio demonstration.

## 3. Tech Stack

- Python
- Streamlit
- Pandas
- Plotly
- LangChain
- Google Gemini API
- python-dotenv

## 4. How to Run Locally

1. Create and activate a virtual environment.

```powershell
python -m venv .venv
.\.venv\Scripts\activate
```

2. Install dependencies.

```powershell
pip install -r requirements.txt
```

3. Configure environment variables.

Create a `.env` file based on `.env.example` and add your Google Gemini API key.

```text
GOOGLE_API_KEY=your_google_api_key_here
GEMINI_MODEL=gemini-2.5-flash
```

4. Start the Streamlit app.

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

## 5. Example Workflow

1. Open the Streamlit app.
2. Upload a CSV or Excel dataset.
3. Run the data analysis step.
4. Review detected fields, KPI summary, risk signals, trends, and segment analysis.
5. Go to the report generation page.
6. Choose report settings:
   - Language: Chinese or English
   - Tone: Executive Summary or Analyst Report
   - Length: Brief or Detailed
7. Generate a markdown business insight report.
8. Review the recommended action plan and data limitations.

## 6. Sample Datasets

The project includes multi-industry sample datasets under `data/sample/`:

| Dataset | File | Business Scenario |
| --- | --- | --- |
| Retail Sales | `data/sample/retail_sales_sample.csv` | Sales, profit, discount risk, and loss-making products |
| SaaS Metrics | `data/sample/saas_metrics_sample.csv` | MRR, ARR, churn, expansion revenue, CAC, and support tickets |
| Logistics Operations | `data/sample/logistics_operations_sample.csv` | Delivery delays, shipping cost, carrier performance, and damage risk |

## 7. Sample Reports

Sample management reports are available under `examples/sample_reports/`.

English reports:

- `examples/sample_reports/retail_sales_report.md`
- `examples/sample_reports/saas_metrics_report.md`
- `examples/sample_reports/logistics_operations_report.md`

Chinese reports:

- `examples/sample_reports/retail_sales_report_zh.md`
- `examples/sample_reports/saas_metrics_report_zh.md`
- `examples/sample_reports/logistics_operations_report_zh.md`

These reports show the intended output style for different industries and demonstrate how findings, evidence, hypotheses, recommendations, and limitations should be separated.

## 8. Demo Screenshots

Screenshots can be added under `assets/` using the following filenames.

### Upload Page

![Upload Page](assets/upload_page.png)

### Analysis Page

![Analysis Page](assets/analysis_page.png)

### Report Settings

![Report Settings](assets/report_settings.png)

### Generated Report

![Generated Report](assets/generated_report.png)

### Dashboard

![Dashboard](assets/dashboard.png)

## 9. Business Report Structure

Generated reports follow a consistent management-report structure:

1. Executive Summary
2. KPI Snapshot
3. Key Insights with Evidence
4. Segment Deep Dive
5. Root Cause Hypotheses
6. Recommended Action Plan
7. Data Limitations

Each key insight is expected to include:

- Finding
- Evidence
- Business implication
- Confidence level

Each recommended action is expected to include:

- Priority
- Action
- Business rationale
- Suggested owner
- Timeframe
- KPI to track

## 10. Project Architecture

```text
app.py
  Streamlit UI, page navigation, upload flow, analysis flow, report generation flow

agents/
  data_analyzer.py
    Field detection, KPI computation, trend analysis, risk detection, top/bottom analysis

  report_generator.py
    Business report schema, derived metrics, evidence-safe report rendering, Gemini report prompt

  file_parser.py
    File parsing helpers

utils/
  file_handler.py
    Upload and file reading utilities

  chart_generator.py
    Plotly chart helpers

data/
  sample/
    Multi-industry sample datasets

  uploads/
    Uploaded files during local usage

  reports/
    Local report output directory

examples/
  sample_reports/
    Example English and Chinese management reports
```

## 11. Current Limitations

- The application works best with structured tabular data.
- Field detection is rule-based and may need manual validation for unusual column names.
- Reports are generated from computed summaries and samples, not full manual audit of every raw record.
- Root cause explanations are treated as hypotheses unless directly supported by available fields.
- Market competition, inventory, customer behavior, product lifecycle, weather, traffic, or operational constraints are not treated as confirmed causes unless the dataset includes supporting fields.
- Gemini API quota or rate limits may trigger local fallback report generation.
- PDF and PPTX export are not yet implemented.

## 12. Roadmap

- Add manual field-mapping correction in the UI.
- Add saved report history.
- Add automatic chart recommendations.
- Add richer time-series trend interpretation.
- Add cohort-style analysis for SaaS datasets.
- Add route and carrier scorecards for logistics datasets.
- Add report export to PDF and PPTX.
- Add data privacy checks and sensitive-field masking.
- Add more robust multilingual report templates.
