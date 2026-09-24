# Project Improvements Log

This document records the real-world considerations and improvements made while turning the project from a basic data summary tool into an AI Business Insight Copilot for enterprise-style reporting.

## Purpose

The project is designed to generate business insight reports from uploaded datasets. The improvements below focus on making the reports more realistic, evidence-safe, industry-aware, and suitable for a GitHub portfolio project.

## Key Principles

- Keep report outputs in markdown.
- Keep changes small and reviewable.
- Do not hardcode API keys.
- Do not remove existing functionality without confirmation.
- Do not invent unsupported business facts.
- Separate data-backed findings from hypotheses.
- Label conclusions by evidence strength and confidence level.
- Use business-specific KPIs instead of generic numeric summaries whenever possible.

## Improvements Made

### 1. Google Gemini Integration

- Updated the project to use Google Gemini through environment variables.
- Added fallback behavior when Gemini generation fails, so the app can still produce a local markdown report.
- Added quota/error handling visibility in the Streamlit app.
- Kept API keys out of source code and `.env` out of Git tracking.

### 2. Structured Business Report Schema

The generated report was upgraded from a basic summary into a structured business report with these sections:

1. Executive Summary
2. KPI Snapshot
3. Key Insights with Evidence
4. Segment Deep Dive
5. Root Cause Hypotheses
6. Recommended Action Plan
7. Data Limitations

Each major insight now includes:

- Finding
- Evidence
- Business Implication
- Confidence Level

Each recommended action now includes:

- Priority
- Action
- Business rationale
- Suggested owner
- Timeframe
- KPI to track

### 3. Evidence-Safe Reporting

- Data-backed findings are labeled as high confidence.
- Correlation or partial evidence is labeled as medium confidence.
- Plausible but unproven explanations are labeled as hypothesis / low confidence.
- The report avoids presenting market competition, inventory clearance, customer behavior, service quality, product lifecycle, or other unsupported causes as confirmed facts.
- Root cause hypotheses include "Data Needed for Validation."
- Final reports include a dedicated Data Limitations section.

### 4. Derived Business Metrics

Added derived metrics for datasets that contain the required fields:

- Loss record ratio
- Loss amount vs total profit
- High-discount loss ratio
- Average order value
- Profit margin
- Discount risk level

These metrics are used in the Executive Summary and KPI Snapshot to make the report more decision-oriented.

### 5. Executive Summary Improvements

The Executive Summary was rewritten to follow a management-oriented structure:

- Overall performance
- Main management issue
- Financial or operational impact
- Priority action
- Confidence / limitation

Generic wording was reduced. Conclusions are now tied to specific metrics where possible.

### 6. KPI Snapshot Polish

- Removed duplicate KPI rows.
- Added consistent numeric formatting:
  - Currency, sales, profit, and cost values use commas and two decimals.
  - Counts use no decimals.
  - Percentages include `%`.
- KPI interpretation is written in business terms, not just definitions.
- Retail-style reports connect profit quality to loss records and discount risk.
- SaaS reports focus on recurring revenue and churn metrics.
- Logistics reports focus on delivery, delay, damage, and shipping cost metrics.

### 7. Segment Deep Dive Improvements

- Replaced long raw top/bottom dumps with compact management tables.
- Each segment table now summarizes:
  - Best-performing object
  - Weakest or risk object
  - Key value
  - Management interpretation
  - Recommended follow-up
- Product and customer analysis focuses on the most important risk objects instead of dumping long names.
- Positive-profit segments are no longer described as profit drags.
- Safer wording is used, such as "relatively weaker profit contribution" and "priority review area."

### 8. Practical Action Plan

The Recommended Action Plan was upgraded to be more practical and evidence-linked.

Examples:

- Review or escalate high-discount loss transactions.
- Audit the lowest-profit product's pricing and discount records.
- Review the weakest region or category by profit.
- Validate numeric anomalies before using them for management decisions.
- Add exception reason tracking for logistics delays and damage.
- Review SaaS retention drivers for the highest-churn plan.

Each action includes owner, timeframe, and KPI to track.

### 9. Report Language Settings

Added report settings in the Streamlit report generation flow:

- Language: Chinese or English
- Tone: Executive Summary or Analyst Report
- Length: Brief or Detailed

Chinese is the default report language because most of the app UI is Chinese.

The selected language controls the full report output, including:

- Headings
- KPI names
- Insight explanations
- Evidence
- Business implications
- Hypotheses
- Recommended actions
- Data limitations

### 10. BusinessInsightAgent Integration

- The report generation flow now checks `st.session_state.business_insights`.
- If `business_insights` exists, it is used as the primary report input.
- If not, the report generator falls back to the existing `analysis_results`.
- This keeps the current app working while allowing richer future business insight modules.

### 11. Sample Datasets

Added three multi-industry sample datasets under `data/sample/`:

- `retail_sales_sample.csv`
- `saas_metrics_sample.csv`
- `logistics_operations_sample.csv`

The datasets are synthetic and designed for testing:

- Retail includes high-discount and loss-making records.
- SaaS includes MRR, ARR, churn, expansion revenue, support tickets, and CAC.
- Logistics includes delivery delays, damage flags, shipping cost pressure, carriers, routes, and warehouses.

### 12. Sample Reports

Added English and Chinese sample reports under `examples/sample_reports/`:

- Retail Sales report
- SaaS Metrics report
- Logistics Operations report

The reports follow the same business report structure and use industry-appropriate KPIs.

### 13. README Portfolio Upgrade

Updated `README.md` to position the project as an AI Business Insight Copilot.

The README now includes:

- Project Overview
- Key Features
- Tech Stack
- How to Run Locally
- Example Workflow
- Sample Datasets
- Sample Reports
- Business Report Structure
- Project Architecture
- Demo Screenshots section
- Current Limitations
- Roadmap

The README also mentions Chinese and English report generation and the multi-industry sample datasets.

### 14. Industry-Aware Report Generation

After testing the generated reports with the sample datasets, SaaS and Logistics reports showed that the previous report generator was too retail/profit-oriented.

The following improvements were added:

- Lightweight industry detection:
  - SaaS if `mrr`, `arr`, and `churn_rate` exist.
  - Logistics if `shipping_cost`, `delivery_time_days`, and `delay_flag` exist.
  - Generic fallback otherwise.
- SaaS-specific analysis:
  - Current MRR
  - Current ARR
  - MRR growth
  - New customers
  - Churned customers
  - Average churn rate
  - Expansion revenue
  - Support tickets
  - Average CAC
  - Plan and customer segment performance
- Logistics-specific analysis:
  - Total shipments
  - Total order value
  - Total shipping cost
  - Shipping cost ratio
  - Average delivery time
  - Delayed shipments
  - Delay rate
  - Damage-flagged shipments
  - Damage rate
  - Region, carrier, route, and warehouse performance
- SaaS reports no longer rewrite `expansion_revenue` as total sales.
- Logistics reports no longer state that the report is weak just because sales or profit fields are missing.
- Gemini prompt rules now change based on detected industry.
- Local markdown fallback also uses industry-aware schemas.

## Current Design Notes

- Retail-style datasets still use the generic sales/profit/discount report logic.
- SaaS and Logistics now receive industry-specific KPI and segment logic.
- Industry-specific logic is intentionally simple and readable, rather than a complex abstraction.
- The app still keeps all existing Streamlit pages and workflows.
- Runtime uploads and generated reports should not be committed to GitHub.

## Suggested Next Steps

1. Add `data/uploads/` and `data/reports/` to `.gitignore`.
2. Rerun the three sample datasets in Streamlit and compare generated reports.
3. Add demo screenshots to `assets/`.
4. Link this improvement log from `README.md`.
5. Consider adding simple tests for industry detection and report schema generation.
