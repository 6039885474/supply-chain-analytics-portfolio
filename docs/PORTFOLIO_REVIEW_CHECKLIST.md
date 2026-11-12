# Portfolio review checklist

Use this checklist to understand, personalize, and verify the portfolio before publishing it as your work. Keep a short record of your changes in each project's README.

## Reproduce the analysis

- [ ] Run `python build_all.py` without editing generated result files by hand.
- [ ] Run both project's validation suites using the commands in their READMEs.
- [ ] Reconcile the top-level dashboard totals to their processed CSVs and SQL outputs.
- [ ] Open both dashboards and exercise every filter, drill-down, and export control present.
- [ ] Confirm that the data source and analysis cutoff are visible and accurate.

## Explain the important decisions

- [ ] Explain why inventory record accuracy uses audited records and an explicit tolerance.
- [ ] Show how due-but-undispatched orders affect dispatch timeliness and overdue backlog.
- [ ] Explain the first-attempt denominator and why it differs from the on-time-delivery cohort.
- [ ] Distinguish return-to-origin from a customer return after delivery.
- [ ] Explain why completed-return duration must be read together with open-return aging.
- [ ] Explain missing cost coverage and demonstrate why an unknown cost is not zero.
- [ ] Trace one rejected record from raw CSV to its quality report and explain the chosen treatment.

## Make and document one meaningful improvement

Pick a business question, change the source analysis, and verify the resulting behavior. Good examples include a sensitivity comparison for count tolerance, return-aging buckets by reason, or a new warehouse exception-priority rule.

- [ ] State the question and expected use of the change.
- [ ] Explain the source-code or SQL change and any trade-off.
- [ ] Add or update a focused validation case for a genuine failure risk.
- [ ] Record the computed before/after analytical result with the same dataset and comparison definition.
- [ ] State what the result means and what it does not establish.

## Prepare the public presentation

- [ ] Add actual GitHub/profile URLs where you choose to show them; do not leave dead links.
- [ ] Use only the synthetic data and fictional facilities provided, or clearly licensed public replacements.
- [ ] Keep the dashboard screenshots synchronized with the committed code and data.
- [ ] If a Power BI or Tableau extension is added, include the real workbook or live link and reconcile its totals.
- [ ] Practice a two-minute walkthrough: operational question, data, method, findings, recommended investigation, and limitations.

## Interview prompts

1. Which denominator would change if a shipment has no first-attempt scan?
2. Would lowering the inventory count tolerance always improve the reported accuracy rate? Why?
3. How could the completed-return average improve while the real backlog gets worse?
4. Which recommendations can this descriptive analysis justify, and which would require an operational experiment?
5. What would have to change to connect this workflow to real WMS, TMS, or SAP data?
