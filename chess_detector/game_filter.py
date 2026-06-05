def parse_time_control(tc: str) -> int:
    """Convert time control string to base seconds. Returns 0 if unparseable."""
    try:
        return int(str(tc).split("+")[0])
    except:
        return 0

def filter_games_by_time_control(pgns: list, min_seconds: int = 180) -> tuple:
    """
    Filter out games below a minimum time control.
    
    min_seconds: minimum base time in seconds
        60  = bullet and above
        180 = blitz and above (default)
        600 = rapid and above
        
    Returns (kept, skipped) lists.
    """
    import chess.pgn
    import io
    
    kept = []
    skipped = []
    
    for pgn in pgns:
        try:
            game = chess.pgn.read_game(io.StringIO(pgn))
            if game is None:
                skipped.append(pgn)
                continue
            tc = game.headers.get("TimeControl", "0")
            base = parse_time_control(tc)
            if base >= min_seconds:
                kept.append(pgn)
            else:
                skipped.append(pgn)
        except:
            skipped.append(pgn)
    
    return kept, skipped
