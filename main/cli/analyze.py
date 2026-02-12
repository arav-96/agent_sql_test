import argparse

from runners.analyze_question import analyze_question


def main():
    parser = argparse.ArgumentParser(
        description="Run end-to-end agentic analysis using DuckDB"
    )

    parser.add_argument(
        "--question",
        type=str,
        required=True,
        help="Natural language question to analyze"
    )

    parser.add_argument(
        "--db",
        type=str,
        required=True,
        help="Path to DuckDB file (e.g., taxi.duckdb)"
    )

    args = parser.parse_args()

    result = analyze_question(
        question=args.question,
        duckdb_path=args.db
    )

    print("\n====================")
    print("QUESTION")
    print("====================")
    print(args.question)

    if "error" in result:
        print("\nERROR:")
        print(result)
        return

    print("\n====================")
    print("PLAN")
    print("====================")
    print(result["plan"])

    print("\n====================")
    print("SUMMARY")
    print("====================")
    print(result["summary"])

    print("\n====================")
    print("DIAGNOSTICS (keys)")
    print("====================")
    for k in result["diagnostics"].keys():
        print("-", k)


if __name__ == "__main__":
    main()
