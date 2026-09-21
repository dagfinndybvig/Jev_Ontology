"""Run just iteration 2 against v4.0 to get feedback signals."""
import convergence_experiment as ce

TICKETS = ce.TICKETS
result = ce.run_iteration("Iteration 2 (v4.0)", TICKETS, "ontology_v4.json")

print("\n\n=== DETAILED FLAGGED TICKETS ===")
for r in result["flagged"]:
    print(f"\n[{r['leaf']} conf={r['conf']:.3f}]")
    print(f"  '{r['ticket']}'")

print("\n\n=== DETAILED LOW-MARGIN ===")
for lm in result["low_margin"]:
    print(f"  {lm['top']}({lm['top_p']:.2f}) vs {lm['second']}({lm['second_p']:.2f}) at {lm['node']}")
    print(f"    '{lm['ticket']}'")
