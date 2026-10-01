"""Run just iteration 1 against v3.0 to get feedback signals for ontology revision."""
import convergence_experiment as ce

TICKETS = ce.TICKETS
def main():
    result = ce.run_iteration("Iteration 1 (baseline)", TICKETS, "ontology_v3.json")
    print("\n\n=== DETAILED FLAGGED TICKETS ===")
    for record in result["flagged"]:
        print(f"\n[{record['leaf']} conf={record['conf']:.3f}]")
        print(f"  '{record['ticket']}'")
    print("\n\n=== DETAILED LOW-MARGIN ===")
    for signal in result["low_margin"]:
        print(f"  {signal['top']}({signal['top_p']:.2f}) vs "
              f"{signal['second']}({signal['second_p']:.2f}) at {signal['node']}")
        print(f"    '{signal['ticket']}'")


if __name__ == "__main__":
    main()
