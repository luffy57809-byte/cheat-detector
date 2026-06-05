import requests
from typing import Optional

def get_chesscom_rating_history(username: str) -> dict:
    """Get full rating history from chess.com for all time controls."""
    url = f"https://api.chess.com/pub/player/{username}/stats"
    resp = requests.get(url, headers={"User-Agent": "chess-cheat-detector/1.0"})
    if resp.status_code != 200:
        return {}
    
    data = resp.json()
    history = {}
    
    for mode in ("chess_bullet", "chess_blitz", "chess_rapid"):
        if mode in data:
            record = data[mode]
            key = mode.replace("chess_", "")
            history[key] = {
                "current":  record.get("last", {}).get("rating"),
                "best":     record.get("best", {}).get("rating"),
                "lowest":   record.get("record", {}).get("loss"),
                "wins":     record.get("record", {}).get("win"),
                "losses":   record.get("record", {}).get("loss"),
                "draws":    record.get("record", {}).get("draw"),
            }
    
    return history


def get_lichess_rating_history(username: str) -> list:
    """Get full rating history from Lichess."""
    url = f"https://lichess.org/api/user/{username}/rating-history"
    resp = requests.get(url, headers={"Accept": "application/json"})
    if resp.status_code != 200:
        return []
    return resp.json()


def detect_rating_spike(username: str, platform: str = "lichess") -> dict:
    """
    Detect suspicious rating spikes in a players history.
    
    A spike is suspicious if:
    - Rating jumped more than 200 points in a short period
    - Win rate suddenly jumped dramatically
    - Performance is far above established rating
    
    Returns a dict with spike info and suspicion score.
    """
    result = {
        "has_spike": False,
        "spike_amount": 0,
        "suspicion_score": 0,
        "details": []
    }

    if platform == "lichess":
        history = get_lichess_rating_history(username)
        
        for category in history:
            name = category.get("name", "")
            points = category.get("points", [])
            
            if len(points) < 10:
                continue
            
            # Each point is [year, month, day, rating]
            ratings = [p[3] for p in points]
            
            # Check for large jumps between consecutive ratings
            for i in range(1, len(ratings)):
                diff = ratings[i] - ratings[i-1]
                if diff > 200:
                    result["has_spike"] = True
                    result["spike_amount"] = max(result["spike_amount"], diff)
                    result["details"].append(
                        f"{name}: +{diff} rating jump detected"
                    )
            
            # Check overall trajectory
            if len(ratings) >= 20:
                early_avg = sum(ratings[:10]) / 10
                recent_avg = sum(ratings[-10:]) / 10
                total_gain = recent_avg - early_avg
                
                if total_gain > 400:
                    result["details"].append(
                        f"{name}: gained {total_gain:.0f} rating points overall"
                    )

    elif platform == "chesscom":
        history = get_chesscom_rating_history(username)
        
        for mode, stats in history.items():
            current = stats.get("current")
            best = stats.get("best")
            
            if current and best:
                diff = best - current
                if diff > 300:
                    result["details"].append(
                        f"{mode}: best rating {best} vs current {current} (diff={diff})"
                    )

    # Calculate suspicion score from spike amount
    spike = result["spike_amount"]
    if spike > 400:
        result["suspicion_score"] = 80
    elif spike > 300:
        result["suspicion_score"] = 60
    elif spike > 200:
        result["suspicion_score"] = 40
    elif spike > 150:
        result["suspicion_score"] = 20
    
    return result
