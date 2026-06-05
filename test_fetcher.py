from chess_detector.fetcher import fetch_games, get_chesscom_profile, get_lichess_profile

# Test with a real public player
# Change these to any real chess.com or lichess username
CHESSCOM_USER = "hikaru"
LICHESS_USER = "DrNykterstein"  # Magnus Carlsen on Lichess

print("=== Testing chess.com profile ===")
ratings = get_chesscom_profile(CHESSCOM_USER)
print(f"{CHESSCOM_USER} ratings: {ratings}")

print("\n=== Testing Lichess profile ===")
ratings = get_lichess_profile(LICHESS_USER)
print(f"{LICHESS_USER} ratings: {ratings}")

print("\n=== Fetching 3 games from chess.com ===")
games = fetch_games(CHESSCOM_USER, platform="chesscom", max_games=3)
print(f"Got {len(games)} games")
if games:
    # Print first 5 lines of first game
    print("\nFirst game preview:")
    for line in games[0].splitlines()[:8]:
        print(" ", line)

print("\n=== Fetching 3 games from Lichess ===")
games = fetch_games(LICHESS_USER, platform="lichess", max_games=3)
print(f"Got {len(games)} games")
if games:
    print("\nFirst game preview:")
    for line in games[0].splitlines()[:8]:
        print(" ", line)
