"""Run just iteration 2 against v4.0 to get feedback signals."""
import convergence_experiment as ce

TICKETS = ce.TICKETS
def main():
    result = ce.run_iteration("Iteration 2 (v4.0)", TICKETS, "ontology_v4.json")
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
