# Offline Evaluation

## Scope

This lightweight evaluation exercises the repository's committed synthetic fixtures and deterministic code paths. It does not instantiate an LLM client, read credentials, or call an external API.

The three fixtures contain 36 rows each:

- Retail: orders with sales, cost, profit, discount, quantity, product, customer, and region fields.
- SaaS: monthly plan and customer-segment snapshots from 2025-01 through 2025-12.
- Logistics: shipment records with order value, shipping cost, delivery time, delay, damage, route, carrier, region, and warehouse fields.

## Metric Semantics

### Retail

Sales and profit are summed across fixture rows. Profit margin is total profit divided by total sales. Loss records have negative profit. High-discount loss records have negative profit and a discount at or above the fixture's 90th-percentile discount threshold.

### SaaS

MRR and ARR are snapshot metrics. `current_mrr` and `current_arr` aggregate the latest available period (`2025-12`) across plans; monthly snapshots are not summed across the full year. MRR growth compares aggregate MRR in the first and latest available months. New customers, churned customers, expansion revenue, and support tickets are period flows and are summed across the available history. Average churn rate and CAC are unweighted row averages.

### Logistics

Each row is one shipment. Delay and damage rates divide flagged shipments by total shipments. Shipping cost ratio divides total shipping cost by total order value. Delivery time is the unweighted row average. `order_value` is monetary and is not treated as an order identifier.

## Results

| Domain | KPI correctness | Report structure | Reliability/fallback | Evidence separation |
| --- | --- | --- | --- | --- |
| Retail | PASS | PASS | PASS | PASS |
| SaaS | PASS | PASS | PASS | PASS |
| Logistics | PASS | PASS | PASS | PASS |

The results above were produced by the offline runner against the committed fixtures. A failed check causes a non-zero process exit status.

## Reproduction

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m evals.run_eval
```

Run the broader deterministic test suite with:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
```

## Limitations

- The evaluation uses three small synthetic fixtures and does not establish production accuracy.
- Field-role inference remains keyword based and may require explicit mappings for unfamiliar schemas.
- Report validation checks structure, bounded schema fidelity, and selected critical KPI values; it is not a general factuality or hallucination detector.
- SaaS churn and CAC averages are not weighted, and the fixtures do not support NRR, GRR, cohort retention, or causal analysis.
- No live provider behavior, latency, quota handling, or model quality is evaluated here.