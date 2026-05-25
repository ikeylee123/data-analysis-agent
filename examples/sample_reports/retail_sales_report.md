# Retail Sales Business Insight Report

## 1. Executive Summary

- **Overall performance:** The sample retail dataset shows positive total profit, with Technology contributing strong high-value orders and Furniture showing the clearest margin pressure.
- **Main management issue:** Several Furniture orders are loss-making, and all of those losses coincide with discounts of 35% or higher.
- **Financial impact:** Loss-making products reduce the quality of overall profit even when total sales remain healthy.
- **Priority action:** Review approval rules for high-discount Furniture orders and audit the lowest-profit products before repeating similar promotions.
- **Confidence / limitation:** High confidence for sales, profit, discount, and product-level findings. Cost driver detail is limited to the provided `cost`, `discount`, and `profit` fields.

## 2. KPI Snapshot

| Metric | Value | Business Interpretation |
| --- | ---: | --- |
| Total sales | 33,130.00 | Healthy sales volume across Technology, Furniture, and Office Supplies. |
| Total profit | 6,588.00 | Profit is positive, but loss-making Furniture transactions reduce profit quality. |
| Profit margin | 19.89% | Positive margin overall; should be reviewed by category because losses are concentrated. |
| Loss-making records | 6 | Losses are not widespread, but they are concentrated enough to justify product-level review. |
| High-discount loss records | 6 | Discount risk is concentrated in loss-making Furniture orders. |

## 3. Key Insights with Evidence

### Furniture is the main profitability review area
- **Finding:** Furniture contains multiple loss-making records.
- **Evidence:** Losses appear in Guest Chair Set, Lounge Sofa, Adjustable Desk, File Cabinet, Training Table, and Cafe Table Set.
- **Business implication:** Furniture discount and cost assumptions should be reviewed before repeating similar offers.
- **Confidence level:** High confidence.

### High discounts overlap with negative profit
- **Finding:** All loss-making orders have discounts between 35% and 50%.
- **Evidence:** File Cabinet has a 42% discount and -50.00 profit; Cafe Table Set has a 50% discount and -90.00 profit.
- **Business implication:** Discount approval thresholds should be reviewed for categories where cost coverage is weak.
- **Confidence level:** High confidence.

### Technology is the strongest profit contributor
- **Finding:** Technology orders generally show stronger profit contribution.
- **Evidence:** Video Conferencing Bar generated 820.00 profit; Security Camera Kit generated 650.00 profit; Desktop Workstation generated 600.00 profit.
- **Business implication:** Technology can be used as a benchmark for margin quality, but this does not explain Furniture losses.
- **Confidence level:** Medium confidence.

## 4. Segment Deep Dive

| Segment | Best-performing object | Weakest or risk object | Key value | Management interpretation | Recommended follow-up |
| --- | --- | --- | ---: | --- | --- |
| Category | Technology | Furniture | Multiple Furniture losses | Furniture is a priority review area, not a confirmed root cause. | Review Furniture margin and discount rules. |
| Product | Video Conferencing Bar | Cafe Table Set | -90.00 profit | Cafe Table Set is a direct loss-making product in this sample. | Audit pricing, cost, and discount records. |
| Region | East / West | South / Central Furniture orders | Several loss records | Losses are visible in more than one region. | Review loss orders by category and region together. |

## 5. Root Cause Hypotheses

| Hypothesis | Evidence Level | Supporting Evidence | Additional Data Needed |
| --- | --- | --- | --- |
| Discounts may be eroding Furniture margins. | Medium | High discounts overlap with negative-profit Furniture orders. | Promotion approval rules, product-level cost policy, target margin thresholds. |
| Furniture cost structure may be less favorable than other categories. | Low / Hypothesis | Furniture has several loss-making records, but cost drivers are not detailed. | Supplier cost, freight cost, handling cost, return rate. |

## 6. Recommended Action Plan

| Priority | Action | Rationale | Owner | Timeframe | KPI to Track |
| --- | --- | --- | --- | --- | --- |
| High | Escalate approval for Furniture discounts at or above 35%. | All loss-making Furniture orders have discounts of 35% or higher. | Sales Operations | 2 weeks | Loss-making order ratio, average discount |
| High | Audit Cafe Table Set, Training Table, and Lounge Sofa pricing. | These products show direct negative profit in the sample. | Finance | 2 weeks | Product profit, gross margin |
| Medium | Compare Technology and Furniture margin structure. | Technology contributes stronger profits while Furniture has losses. | Sales Director | 1 month | Category profit margin |

## 7. Data Limitations

- The sample has 36 rows, so conclusions should be treated as directional.
- The dataset does not include promotion goals, supplier terms, return rates, or inventory data.
- Customer behavior and market competition are not included and should not be treated as confirmed causes.
