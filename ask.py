"""Ask a question from the command line.

    python ask.py "Which region had the most new-home sales in 2024?"
    python ask.py            # interactive mode
"""

import argparse

from agent import HousingAgent, Result


def format_table(columns: list, rows: list, limit: int = 20) -> str:
    cells = [columns] + [[str(v) for v in r] for r in rows[:limit]]
    widths = [max(len(row[i]) for row in cells) for i in range(len(columns))]
    lines = ["  ".join(v.ljust(w) for v, w in zip(row, widths)) for row in cells]
    lines.insert(1, "  ".join("-" * w for w in widths))
    if len(rows) > limit:
        lines.append(f"... {len(rows) - limit} more rows")
    return "\n".join(lines)


def show(result: Result, show_sql: bool) -> None:
    if result.error:
        print(f"Error: {result.error}")
    if result.answer:
        print(f"\n{result.answer}\n")
    if show_sql and result.sql:
        print(f"SQL:\n{result.sql}\n")
    if result.columns:
        print(format_table(result.columns, result.rows) + "\n")
    print(
        f"[{result.latency_s}s | {result.input_tokens + result.output_tokens} tokens | "
        f"${result.cost_usd:.4f} | {result.attempts} attempt(s)]"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Ask questions about US housing market data.")
    parser.add_argument("question", nargs="?", help="Leave empty for interactive mode.")
    parser.add_argument("--no-sql", action="store_true", help="Hide the generated SQL.")
    args = parser.parse_args()

    agent = HousingAgent()
    if args.question:
        show(agent.ask(args.question), not args.no_sql)
        return

    print("Ask about US new-home sales, starts, prices, supply or mortgage rates. Ctrl+C to quit.")
    while True:
        try:
            question = input("\n> ").strip()
        except (KeyboardInterrupt, EOFError):
            break
        if question:
            show(agent.ask(question), not args.no_sql)


if __name__ == "__main__":
    main()
