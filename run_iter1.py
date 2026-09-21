"""Run just iteration 1 against v3.0 to get feedback signals for ontology revision."""
import convergence_experiment as ce

TICKETS = ce.TICKETS
result = ce.run_iteration("Iteration 1 (baseline)", TICKETS, "ontology_v3.json")

print("\n\n=== DETAILED FLAGGED TICKETS ===")
for r in result["flagged"]:
    print(f"\n[{r['leaf']} conf={r['conf']:.3f}]")
    print(f"  '{r['ticket']}'")

print("\n\n=== DETAILED LOW-MARGIN ===")
for lm in result["low_margin"]:
    print(f"  {lm['top']}({lm['top_p']:.2f}) vs {lm['second']}({lm['second_p']:.2f}) at {lm['node']}")
    print(f"    '{lm['ticket']}'")
