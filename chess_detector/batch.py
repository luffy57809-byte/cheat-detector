from chess_detector.fetcher import fetch_games, get_chesscom_profile, get_lichess_profile
from chess_detector.core.analyzer import analyze_pgn
from chess_detector.scorer import SuspicionScorer
from chess_detector.database import init_db, save_player, save_game, save_report, is_game_analyzed, get_player_average_score
from chess_detector.checkpoint import save_checkpoint, load_checkpoint, clear_checkpoint

VARIANT_KEYWORDS = ["Chess960", "Antichess", "Atomic", "Horde", "KingOfTheHill", "ThreeCheck"]

def batch_analyze(username: str, platform: str = "auto", max_games: int = 20, rating: int = None, depth: int = 15, min_time_control: int = 0):
    init_db()
    scorer = SuspicionScorer()
    reports = []
    skipped_variants = 0
    skipped_cached = 0
    completed_ids = []

    print(f"\n{'='*50}")
    print(f"  Batch analysis: {username} on {platform}")
    print(f"  Max games: {max_games} | Depth: {depth}")
    print(f"{'='*50}")

    # Get rating
    if rating is None:
        if platform in ("chesscom", "auto"):
            r = get_chesscom_profile(username)
            if r:
                rating = r.get("blitz") or r.get("rapid") or r.get("bullet")
        if rating is None and platform in ("lichess", "auto"):
            r = get_lichess_profile(username)
            if r:
                rating = r.get("blitz") or r.get("rapid") or r.get("bullet")
        if rating is None:
            rating = 1500

    print(f"  Rating: {rating}")
    save_player(username, platform, rating)

    # Check for existing checkpoint
    checkpoint = load_checkpoint(username, platform)
    if checkpoint:
        print(f"  Resuming from checkpoint ({len(checkpoint['completed_game_ids'])} games already done)")
        completed_ids = checkpoint["completed_game_ids"]
        games = checkpoint["remaining_pgns"]
    else:
        games = fetch_games(username, platform=platform, max_games=max_games)
        if not games:
            print("  No games found.")
            return []

    print(f"  Games to process: {len(games)}\n")

    for i, pgn in enumerate(games):
        print(f"  [{i+1}/{len(games)}] ", end="", flush=True)

        # Skip variants
        if any(v in pgn for v in VARIANT_KEYWORDS):
            print("skipping variant")
            skipped_variants += 1
            continue

        try:
            analysis = analyze_pgn(pgn, depth=depth)
        except Exception as e:
            print(f"analysis error: {e}")
            # Save checkpoint so we can resume
            save_checkpoint(username, platform, completed_ids, games[i+1:])
            continue

        # Skip already analyzed
        if is_game_analyzed(analysis.game_id) or analysis.game_id in completed_ids:
            print(f"already analyzed ({analysis.game_id})")
            skipped_cached += 1
            continue

        target = username.lower()
        color = "white" if target in analysis.white_username.lower() else "black"

        try:
            report = scorer.score(analysis, username, color, rating, pgn_text=pgn)
            save_game(analysis, pgn, platform)
            save_report(report, platform)
            reports.append(report)
            completed_ids.append(analysis.game_id)
            # Save checkpoint after every game
            save_checkpoint(username, platform, completed_ids, games[i+1:])
            print(f"{analysis.game_id} | {report.verdict} ({report.overall_score:.1f}/100)")
        except Exception as e:
            print(f"scoring error: {e}")
            save_checkpoint(username, platform, completed_ids, games[i+1:])
            continue

    # All done — clear checkpoint
    clear_checkpoint(username, platform)

    # Summary
    print(f"\n{'='*50}")
    print(f"  BATCH SUMMARY")
    print(f"{'='*50}")
    print(f"  Analyzed   : {len(reports)}")
    print(f"  Cached     : {skipped_cached}")
    print(f"  Variants   : {skipped_variants}")

    if reports:
        avg = sum(r.overall_score for r in reports) / len(reports)
        cheating   = sum(1 for r in reports if r.verdict == "likely cheating")
        suspicious = sum(1 for r in reports if r.verdict == "suspicious")
        clean      = len(reports) - cheating - suspicious

        print(f"  Clean      : {clean}")
        print(f"  Suspicious : {suspicious}")
        print(f"  Cheating   : {cheating}")
        print(f"  Avg score  : {avg:.1f}/100")

        if avg >= 60:
            print(f"\n  VERDICT: LIKELY CHEATING")
        elif avg >= 30:
            print(f"\n  VERDICT: SUSPICIOUS")
        else:
            print(f"\n  VERDICT: CLEAN")

    return reports
