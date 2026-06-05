from chess_detector.batch import batch_analyze
from chess_detector.pgn_upload import analyze_pgn_file

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage:")
        print("  Analyze by username : python main.py <username> <platform> <max_games> [min_tc_seconds]")
        print("  Analyze PGN file    : python main.py --pgn <file.pgn> [username] [rating]")
        print("  Export JSON         : python main.py --export-json [username]")
        print("  Export CSV          : python main.py --export-csv [username]")
        print("  Player summary      : python main.py --summary <username>")
        sys.exit(1)

    if sys.argv[1] == "--pgn":
        filepath = sys.argv[2] if len(sys.argv) > 2 else None
        username = sys.argv[3] if len(sys.argv) > 3 else None
        rating   = int(sys.argv[4]) if len(sys.argv) > 4 else None
        analyze_pgn_file(filepath, username=username, rating=rating)

    elif sys.argv[1] == "--export-json":
        from chess_detector.export import export_json
        username = sys.argv[2] if len(sys.argv) > 2 else None
        path = f"{username}_reports.json" if username else "all_reports.json"
        export_json(username=username, output_path=path)

    elif sys.argv[1] == "--export-csv":
        from chess_detector.export import export_csv
        username = sys.argv[2] if len(sys.argv) > 2 else None
        path = f"{username}_reports.csv" if username else "all_reports.csv"
        export_csv(username=username, output_path=path)

    elif sys.argv[1] == "--summary":
        from chess_detector.export import export_player_summary
        username = sys.argv[2] if len(sys.argv) > 2 else None
        if not username:
            print("Please provide a username.")
            sys.exit(1)
        summary = export_player_summary(username)
        if summary:
            print(f"\nOverall verdict : {summary['overall_verdict'].upper()}")
            print(f"Avg score       : {summary['avg_score']}/100")
            print(f"Games analyzed  : {summary['games_analyzed']}")
            print(f"\nFeature averages:")
            for name, avg in summary["feature_averages"].items():
                print(f"  {name:<30} {avg}")

    else:
        username         = sys.argv[1]
        platform         = sys.argv[2] if len(sys.argv) > 2 else "auto"
        max_games        = int(sys.argv[3]) if len(sys.argv) > 3 else 5
        min_time_control = int(sys.argv[4]) if len(sys.argv) > 4 else 0
        batch_analyze(username, platform=platform, max_games=max_games, min_time_control=min_time_control)
