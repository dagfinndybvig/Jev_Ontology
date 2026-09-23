"""Phase 2 baseline comparison: three systems against review ground truth.

Systems:
  1. cascade      -- Pixtral description + Jev (raw answers in
                     humanoid_pilot_results.json; the production path)
  2. pixtral_direct -- Pixtral asked directly (baseline_pixtral_direct_results.json,
                     from baseline_pixtral_direct.py; included when present)
  3. keyword      -- a trivial keyword classifier on the same descriptions,
                     always fully confident (no calibration by construction)

Ground truth: the manual_correction labels (85 reviewed records).

Metrics per system: per-facet accuracy, pooled facet-answer accuracy by
confidence bin, ECE, flag rate at the 0.7 threshold (= review burden),
and errors caught at the threshold.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
CASCADE_RESULTS = os.path.join(HERE, "humanoid_pilot_results.json")
DIRECT_RESULTS = os.path.join(HERE, "baseline_pixtral_direct_results.json")
FACETS = ["contains_human", "contains_robot", "contains_android", "primary_subject", "representation"]
THRESHOLD = 0.7
BINS = [(0.0, 0.5), (0.5, 0.7), (0.7, 0.9), (0.9, 1.0001)]

TEXT_WORDS = ["text", "screenshot", "terminal", "code", "website", "document", "headline", "list of"]
RENDER_WORDS = ["render", "3d", "statue", "figurine", "sculpture"]
ILLUS_WORDS = ["illustration", "cartoon", "comic", "drawing", "painting", "sketch", "anime", "poster"]
PHOTO_WORDS = ["photograph", "photo"]
HUMAN_WORDS = ["man", "woman", "person", "people", "human", "face", "child", "boy", "girl",
               "team", "crowd", "character", "figure"]
ROBOT_WORDS = ["robot", "automaton", "mecha"]
ANDROID_WORDS = ["android"]


def description_body(desc):
    """Drop the vision prompt's preamble line ('This image does not consist
    of text...') so its words do not trigger the text keywords."""
    lines = [ln for ln in desc.split("\n") if ln.strip()]
    if lines and lines[0].lower().startswith("this image"):
        lines = lines[1:]
    return " ".join(lines).lower()


def keyword_classify(desc):
    body = description_body(desc)
    is_text = any(w in body for w in TEXT_WORDS)
    if is_text:
        rep = "text_screenshot"
    elif any(w in body for w in RENDER_WORDS):
        rep = "statue_or_render"
    elif any(w in body for w in ILLUS_WORDS):
        rep = "illustration"
    elif any(w in body for w in PHOTO_WORDS):
        rep = "photograph"
    else:
        rep = "other"
    has_human = rep != "text_screenshot" and any(w in body for w in HUMAN_WORDS)
    has_robot = any(w in body for w in ROBOT_WORDS)
    has_android = any(w in body for w in ANDROID_WORDS)
    if has_android:
        subject = "android"
    elif has_robot and has_human:
        subject = "multiple"
    elif has_robot:
        subject = "robot"
    elif has_human:
        subject = "human"
    else:
        subject = "none"
    return {
        "contains_human": {"choice": "yes" if has_human else "no", "confidence": 1.0},
        "contains_robot": {"choice": "yes" if has_robot else "no", "confidence": 1.0},
        "contains_android": {"choice": "yes" if has_android else "no", "confidence": 1.0},
        "primary_subject": {"choice": subject, "confidence": 1.0},
        "representation": {"choice": rep, "confidence": 1.0},
    }


def load_labeled():
    with open(CASCADE_RESULTS, "r", encoding="utf-8") as f:
        cascade = json.load(f)
    labeled = {}
    for name, rec in cascade.items():
        mc = rec.get("manual_correction")
        if not mc or rec.get("status") != "ok":
            continue
        labeled[name] = {
            "description": rec.get("description", ""),
            "truth": mc["correct"],
            "cascade": {f: {"choice": rec[f]["choice"], "confidence": rec[f]["confidence"]}
                        for f in FACETS if f in rec},
        }
    return labeled


def load_direct(labeled):
    if not os.path.exists(DIRECT_RESULTS):
        return {}
    with open(DIRECT_RESULTS, "r", encoding="utf-8") as f:
        raw = json.load(f)
    out = {}
    for name in labeled:
        rec = raw.get(name, {})
        if rec.get("status") == "ok" and rec.get("answer"):
            out[name] = rec["answer"]
    return out


def evaluate(name, answers, labeled):
    """answers: {filename: {facet: {choice, confidence}}}"""
    per_facet = {f: [0, 0] for f in FACETS}
    pooled = []  # (confidence, correct)
    for fname, rec in labeled.items():
        truth = rec["truth"]
        ans = answers.get(fname, {})
        for f in FACETS:
            if f not in ans:
                continue
            correct = ans[f]["choice"] == truth[f]
            per_facet[f][1] += 1
            per_facet[f][0] += correct
            pooled.append((ans[f]["confidence"], correct))
    n = len(pooled)
    acc = sum(c for _, c in pooled) / n if n else 0.0
    # ECE: 10 equal-width bins on confidence
    ece = 0.0
    for b in range(10):
        lo, hi = b / 10, (b + 1) / 10
        inb = [(c, ok) for c, ok in pooled if lo <= c < hi or (b == 9 and c == 1.0)]
        if inb:
            ece += len(inb) / n * abs(sum(ok for _, ok in inb) / len(inb) - (lo + hi) / 2)
    # routing at the threshold
    flagged = wrong = caught = confident_wrong = 0
    for fname, rec in labeled.items():
        truth = rec["truth"]
        ans = answers.get(fname, {})
        confs = [ans[f]["confidence"] for f in FACETS if f in ans]
        any_wrong = any(f in ans and ans[f]["choice"] != truth[f] for f in FACETS)
        if any(c < THRESHOLD for c in confs):
            flagged += 1
        if any_wrong:
            wrong += 1
            if any(f in ans and ans[f]["choice"] != truth[f] and ans[f]["confidence"] < THRESHOLD
                   for f in FACETS):
                caught += 1
            else:
                confident_wrong += 1
    bin_table = []
    for lo, hi in BINS:
        inb = [(c, ok) for c, ok in pooled if lo <= c < hi]
        if inb:
            bin_table.append((f"{lo:.1f}-{hi:.1f}", sum(ok for _, ok in inb), len(inb)))
    return {
        "name": name,
        "n_records": len(answers),
        "per_facet": {f: tuple(v) for f, v in per_facet.items()},
        "pooled_acc": acc,
        "ece": ece,
        "flag_rate": flagged / len(labeled),
        "wrong_records": wrong,
        "caught": caught,
        "confident_wrong": confident_wrong,
        "bins": bin_table,
    }


def report(ev):
    print(f"\n=== {ev['name']} (n={ev['n_records']} labeled records) ===")
    print("Per-facet accuracy:")
    for f in FACETS:
        ok, n = ev["per_facet"][f]
        print(f"  {f}: {ok}/{n} ({ok / n * 100:.0f}%)" if n else f"  {f}: no data")
    print(f"Pooled facet-answer accuracy: {ev['pooled_acc'] * 100:.0f}%  ECE: {ev['ece']:.3f}")
    print("Accuracy by confidence bin:")
    for label, ok, n in ev["bins"]:
        print(f"  {label}: {ok}/{n} ({ok / n * 100:.0f}%)")
    print(f"Review burden at {THRESHOLD}: {ev['flag_rate'] * 100:.0f}% of records flagged")
    print(f"Wrong records: {ev['wrong_records']}, caught by threshold: {ev['caught']}, "
          f"confident (silent) errors: {ev['confident_wrong']}")


def main():
    labeled = load_labeled()
    print(f"Labeled records (ground truth): {len(labeled)}")

    systems = []
    kw = {name: keyword_classify(rec["description"]) for name, rec in labeled.items()}
    systems.append(evaluate("keyword baseline (trivial, always confident)", kw, labeled))
    cascade = {name: rec["cascade"] for name, rec in labeled.items()}
    systems.append(evaluate("cascade: Pixtral description + Jev", cascade, labeled))
    direct = load_direct(labeled)
    if direct:
        systems.append(evaluate("Pixtral asked directly", direct, labeled))
    else:
        print("\nPixtral-direct: no results yet (run baseline_pixtral_direct.py; "
              "last attempt failed with HTTP 402 Payment Required)")

    for ev in systems:
        report(ev)

    print("\n=== Head-to-head ===")
    hdr = f"{'system':45} {'acc':>5} {'ECE':>6} {'burden':>7} {'wrong':>6} {'caught':>7} {'silent':>7}"
    print(hdr)
    for ev in systems:
        print(f"{ev['name']:45} {ev['pooled_acc'] * 100:4.0f}% {ev['ece']:6.3f} "
              f"{ev['flag_rate'] * 100:6.0f}% {ev['wrong_records']:6d} "
              f"{ev['caught']:7d} {ev['confident_wrong']:7d}")


if __name__ == "__main__":
    main()
