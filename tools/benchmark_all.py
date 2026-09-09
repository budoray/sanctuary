"""Run the headless benchmark across all classes and print a summary."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from batch_headless import run_one  # noqa: E402

CLASSES = ["fighter", "cleric", "thief", "magic_user"]


def main():
    parser = argparse.ArgumentParser(description="Benchmark all starting classes in Sanctuary")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--url", default="http://127.0.0.1:8700")
    parser.add_argument("--rounds", type=int, default=40)
    parser.add_argument("--ticker-speed", type=float, default=60.0)
    parser.add_argument("--fps", type=float, default=60.0)
    parser.add_argument("--markdown", action="store_true", help="Output a markdown summary table")
    args = parser.parse_args()

    results: dict[str, dict] = {}
    for class_id in CLASSES:
        print(f"\n{'=' * 60}")
        print(f"Class: {class_id}")
        print("=" * 60, flush=True)
        wins = 0
        defeats = 0
        unknown = 0
        crashes = 0
        times = []
        for i in range(1, args.runs + 1):
            print(f"\n--- Run {i}/{args.runs} ---", flush=True)
            res = run_one(args.url, args.rounds, args.ticker_speed, args.fps, class_id)
            # If the browser crashed, retry once after a short cooldown.
            if res["returncode"] != 0 and ("browser has been closed" in res["stderr"] or "Target page" in res["stderr"]):
                crashes += 1
                print(f"Run {i}: browser crashed, retrying once...", flush=True)
                res = run_one(args.url, args.rounds, args.ticker_speed, args.fps, class_id)
            outcome = res["outcome"].lower()
            is_win = "win" in outcome or "cleared" in outcome or "exit open" in outcome or "victory" in outcome
            is_defeat = "defeat" in outcome or "fallen" in outcome or "died" in outcome or "unconscious" in outcome
            if is_win:
                wins += 1
                print(f"Run {i}: WIN (HP {res['final_hp']}, {res['web_seconds']:.1f}s)", flush=True)
            elif is_defeat:
                defeats += 1
                print(f"Run {i}: DEFEAT (HP {res['final_hp']}, {res['web_seconds']:.1f}s)", flush=True)
            else:
                unknown += 1
                print(f"Run {i}: UNKNOWN ({res['outcome']}, HP {res['final_hp']}, {res['web_seconds']:.1f}s)", flush=True)
            times.append(res["web_seconds"])
        results[class_id] = {
            "wins": wins,
            "defeats": defeats,
            "unknown": unknown,
            "crashes": crashes,
            "times": times,
        }

    print("\n" + "=" * 60)
    print("CROSS-CLASS SUMMARY")
    print("=" * 60)
    if args.markdown:
        print("| Class | Runs | Wins | Defeats | Unknown | Crashes | Win % | Avg Time (s) |")
        print("|-------|------|------|---------|---------|---------|-------|--------------|")
    for class_id in CLASSES:
        r = results[class_id]
        total = args.runs
        win_pct = 100 * r["wins"] / total if total else 0
        avg_time = sum(r["times"]) / len(r["times"]) if r["times"] else 0
        if args.markdown:
            print(f"| {class_id} | {total} | {r['wins']} | {r['defeats']} | {r['unknown']} | {r.get('crashes', 0)} | {win_pct:.0f}% | {avg_time:.1f} |")
        else:
            print(f"{class_id:12}  wins {r['wins']}/{total} ({win_pct:.0f}%)  defeats {r['defeats']}  unknown {r['unknown']}  crashes {r.get('crashes', 0)}  avg {avg_time:.1f}s")
    print("=" * 60)


if __name__ == "__main__":
    main()
