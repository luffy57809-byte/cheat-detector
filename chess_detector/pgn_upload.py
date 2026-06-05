import os
import io
import chess.pgn
from chess_detector.core.analyzer import analyze_pgn
from chess_detector.scorer import SuspicionScorer
from chess_detector.database import init_db, save_game, save_report, is_game_analyzed
from chess_detector.fetcher import split_pgn

def analyze_pgn_file(filepath: str, username: str = None, rating: int = None, depth: int = 15):
    """
    Analyze games from a PGN file uploaded by the user.
    
    filepath : path to the .pgn file
    username : player to focus on (if None, analyzes both sides)
    rating   : player rating (if None, tries to detect from PGN headers)
    """
    init_db()
    scorer = SuspicionScorer()
    reports = []

    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        return []

    print(f"\n{'='*50}")
    print(f"  PGN Upload Analysis")
    print(f"  File: {filepath}")
    print(f"{'='*50}")

    # Read and split into individual games
    raw = open(filepath, encoding="utf-8", errors="replace").read()
    games = split_pgn(raw)
    games = [g for g in games if g.strip()]
    print(f"  Found {len(games)} game(s) in file\n")

    for i, pgn in enumerate(games):
        print(f"  [{i+1}/{len(games)}] ", end="", flush=True)

        try:
            analysis = analyze_pgn(pgn, depth=depth)
        except Exception as e:
            print(f"analysis error: {e}")
            continue

        # Detect which color to analyze
        if username:
            target = username.lower()
            white = analysis.white_username.lower()
            black = analysis.black_username.lower()
            if target in white:
                colors = ["white"]
            elif target in black:
                colors = ["black"]
            else:
                print(f"username {username} not found in game, analyzing both sides")
                colors = ["white", "black"]
        else:
            colors = ["white", "black"]

        # Try to get rating from PGN headers if not provided
        effective_rating = rating
        if effective_rating is None:
            game_obj = chess.pgn.read_game(io.StringIO(pgn))
            if game_obj:
                for color in colors:
                    elo_key = "WhiteElo" if color == "white" else "BlackElo"
                    elo = game_obj.headers.get(elo_key)
                    if elo and elo.isdigit():
                        effective_rating = int(elo)
                        break

        for color in colors:
            player = analysis.white_username if color == "white" else analysis.black_username
            display_name = username or player

            if is_game_analyzed(analysis.game_id):
                print(f"already analyzed ({analysis.game_id})")
                continue

            try:
                report = scorer.score(analysis, display_name, color, effective_rating, pgn_text=pgn)
                save_game(analysis, pgn, "pgn_upload")
                save_report(report, "pgn_upload")
                reports.append(report)
                print(f"{analysis.game_id} | {color} | {report.verdict} ({report.overall_score:.1f}/100)")
                print(report.summary())
            except Exception as e:
                print(f"scoring error: {e}")

    # Summary
    if reports:
        avg = sum(r.overall_score for r in reports) / len(reports)
        cheating  = sum(1 for r in reports if r.verdict == "likely cheating")
        suspicious = sum(1 for r in reports if r.verdict == "suspicious")
        clean = len(reports) - cheating - suspicious

        print(f"\n{'='*50}")
        print(f"  PGN UPLOAD SUMMARY")
        print(f"{'='*50}")
        print(f"  Games analyzed : {len(reports)}")
        print(f"  Clean          : {clean}")
        print(f"  Suspicious     : {suspicious}")
        print(f"  Likely cheating: {cheating}")
        print(f"  Avg score      : {avg:.1f}/100")
        if avg >= 60:
            print(f"\n  VERDICT: LIKELY CHEATING")
        elif avg >= 30:
            print(f"\n  VERDICT: SUSPICIOUS")
        else:
            print(f"\n  VERDICT: CLEAN")

    return reports
