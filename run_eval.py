"""Score the agent against questions with known answers.

A question passes when the agent's query result matches the reference query's result:
same row count, and every reference column appears among the agent's columns
(order-insensitive, numbers compared with a small tolerance). Extra columns are allowed.
Questions marked expect_decline pass only if the agent says the data can't answer them.

    python run_eval.py            # calls Claude
    python run_eval.py --oracle   # uses the reference SQL as the "prediction" to test the harness for free
"""

import argparse
import datetime as dt
import decimal
import json
import math
import statistics

from agent import HousingAgent, Result


def normalize(v):
    if isinstance(v, (int, float, decimal.Decimal)) and not isinstance(v, bool):
        return (0, float(v))
    if isinstance(v, (dt.date, dt.datetime)):
        return (1, v.isoformat()[:10])
    return (1, str(v).strip().lower())


def same_value(a, b) -> bool:
    if a[0] == 0 and b[0] == 0:
        return math.isclose(a[1], b[1], rel_tol=2e-3, abs_tol=0.01)
    return a == b


def same_column(ref: tuple, pred: tuple) -> bool:
    ref, pred = sorted(map(normalize, ref)), sorted(map(normalize, pred))
    return all(same_value(a, b) for a, b in zip(ref, pred))


def results_match(ref_rows: list, pred_rows: list) -> bool:
    if len(ref_rows) != len(pred_rows) or not ref_rows:
        return False
    ref_cols, pred_cols = list(zip(*ref_rows)), list(zip(*pred_rows))
    return all(any(same_column(r, p) for p in pred_cols) for r in ref_cols)


def grade(case: dict, result: Result, agent: HousingAgent) -> str:
    if case.get("expect_decline"):
        return "pass" if result.declined else "should_decline"
    if result.declined:
        return "wrongly_declined"
    if result.error:
        return "sql_error"
    _, ref_rows = agent.run_sql(case["reference_sql"])
    return "pass" if results_match(ref_rows, result.rows) else "wrong_result"


def run_oracle(agent: HousingAgent, case: dict) -> Result:
    result = Result(question=case["question"], attempts=1)
    if case.get("expect_decline"):
        result.declined = True
    else:
        result.sql = case["reference_sql"]
        result.columns, result.rows = agent.run_sql(result.sql)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--oracle", action="store_true", help="Score the reference SQL itself (no API calls).")
    parser.add_argument("--questions", default="eval_questions.json")
    parser.add_argument("--out", default="eval_results.json")
    args = parser.parse_args()

    cases = json.load(open(args.questions, encoding="utf-8"))
    agent = HousingAgent(model="oracle") if args.oracle else HousingAgent()

    records = []
    for case in cases:
        result = run_oracle(agent, case) if args.oracle else agent.ask(case["question"], explain=False)
        outcome = grade(case, result, agent)
        records.append({"id": case["id"], "outcome": outcome, **result.to_dict()})
        print(f"{'PASS' if outcome == 'pass' else 'FAIL':4}  {case['id']:<20} {outcome:<16} "
              f"{result.latency_s:>5.1f}s  ${result.cost_usd:.4f}  attempts={result.attempts}")

    passed = sum(r["outcome"] == "pass" for r in records)
    latencies = [r["latency_s"] for r in records]
    failures = {}
    for r in records:
        if r["outcome"] != "pass":
            failures[r["outcome"]] = failures.get(r["outcome"], 0) + 1

    summary = {
        "model": agent.model,
        "accuracy": f"{passed}/{len(records)}",
        "accuracy_pct": round(100 * passed / len(records), 1),
        "latency_p50_s": round(statistics.median(latencies), 2),
        "latency_max_s": round(max(latencies), 2),
        "total_cost_usd": round(sum(r["cost_usd"] for r in records), 4),
        "retries_used": sum(r["attempts"] > 1 for r in records),
        "failures": failures,
    }
    print("\n" + json.dumps(summary, indent=2))
    json.dump({"summary": summary, "results": records}, open(args.out, "w", encoding="utf-8"), indent=2)
    print(f"Saved {args.out}")


if __name__ == "__main__":
    main()
