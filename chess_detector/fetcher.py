import requests
import time
from typing import Optional

# ------------------------------------------------
# Chess.com API
# ------------------------------------------------

def get_chesscom_games(username: str, max_games: int = 20) -> list[str]:
    """
    Fetch recent games from chess.com for a username.
    Returns a list of PGN strings.
    """
    print(f"Fetching chess.com games for {username}...")
    
    # Get list of available monthly archives
    archives_url = f"https://api.chess.com/pub/player/{username}/games/archives"
    headers = {"User-Agent": "chess-cheat-detector/1.0"}
    
    resp = requests.get(archives_url, headers=headers)
    if resp.status_code == 404:
        print(f"User {username} not found on chess.com")
        return []
    if resp.status_code != 200:
        print(f"Chess.com error: {resp.status_code}")
        return []
    
    archives = resp.json().get("archives", [])
    if not archives:
        print("No games found.")
        return []
    
    pgns = []
    # Start from most recent archive and work backwards
    for archive_url in reversed(archives):
        if len(pgns) >= max_games:
            break
        
        games_resp = requests.get(archive_url + "/pgn", headers=headers)
        if games_resp.status_code != 200:
            continue
        
        # Chess.com returns one big PGN file with all games
        # Split it into individual games
        raw = games_resp.text
        individual_games = split_pgn(raw)
        
        for game in individual_games:
            if len(pgns) >= max_games:
                break
            if game.strip():
                pgns.append(game.strip())
        
        time.sleep(0.5)  # Be polite to the API
    
    print(f"Found {len(pgns)} games from chess.com")
    return pgns


# ------------------------------------------------
# Lichess API
# ------------------------------------------------

def get_lichess_games(username: str, max_games: int = 20) -> list[str]:
    """
    Fetch recent games from Lichess for a username.
    Returns a list of PGN strings.
    """
    print(f"Fetching Lichess games for {username}...")
    
    url = f"https://lichess.org/api/games/user/{username}"
    headers = {"Accept": "application/x-chess-pgn"}
    params = {
        "max": max_games,
        "clocks": "true",    # Include clock times in PGN comments
        "opening": "false",
    }
    
    resp = requests.get(url, headers=headers, params=params, stream=True)
    if resp.status_code == 404:
        print(f"User {username} not found on Lichess")
        return []
    if resp.status_code != 200:
        print(f"Lichess error: {resp.status_code}")
        return []
    
    # Lichess streams NDJSON or PGN — we asked for PGN
    raw = resp.text
    pgns = split_pgn(raw)
    pgns = [p.strip() for p in pgns if p.strip()]
    
    print(f"Found {len(pgns)} games from Lichess")
    return pgns


# ------------------------------------------------
# Auto-detect platform
# ------------------------------------------------

def fetch_games(username: str, platform: str = "auto", max_games: int = 20) -> list[str]:
    """
    Fetch games from chess.com, lichess, or both.
    
    platform: "chesscom", "lichess", or "auto" (tries both)
    """
    if platform == "chesscom":
        return get_chesscom_games(username, max_games)
    elif platform == "lichess":
        return get_lichess_games(username, max_games)
    else:
        # Try both and combine
        games = []
        games += get_chesscom_games(username, max_games // 2)
        games += get_lichess_games(username, max_games // 2)
        return games


# ------------------------------------------------
# Helper: split a multi-game PGN into individual games
# ------------------------------------------------

def split_pgn(raw: str) -> list[str]:
    """
    Split a PGN string containing multiple games into a list of individual PGNs.
    Games are separated by a blank line before the next [Event tag.
    """
    games = []
    current = []
    
    for line in raw.splitlines():
        if line.startswith("[Event ") and current:
            # Start of a new game — save the previous one
            games.append("\n".join(current))
            current = [line]
        else:
            current.append(line)
    
    if current:
        games.append("\n".join(current))
    
    return games


# ------------------------------------------------
# Quick info fetchers
# ------------------------------------------------

def get_chesscom_profile(username: str) -> Optional[dict]:
    """Get basic profile info including rating from chess.com."""
    url = f"https://api.chess.com/pub/player/{username}/stats"
    resp = requests.get(url, headers={"User-Agent": "chess-cheat-detector/1.0"})
    if resp.status_code != 200:
        return None
    
    data = resp.json()
    ratings = {}
    
    for mode in ("chess_bullet", "chess_blitz", "chess_rapid", "chess_daily"):
        if mode in data:
            last = data[mode].get("last", {})
            ratings[mode.replace("chess_", "")] = last.get("rating")
    
    return ratings


def get_lichess_profile(username: str) -> Optional[dict]:
    """Get basic profile info including rating from Lichess."""
    url = f"https://lichess.org/api/user/{username}"
    resp = requests.get(url, headers={"Accept": "application/json"})
    if resp.status_code != 200:
        return None
    
    data = resp.json()
    perfs = data.get("perfs", {})
    ratings = {}
    
    for mode in ("bullet", "blitz", "rapid", "classical"):
        if mode in perfs:
            ratings[mode] = perfs[mode].get("rating")
    
    return ratings
