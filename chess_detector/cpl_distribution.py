import math
import statistics
from typing import Optional

def compute_cpl_distribution(moves: list) -> dict:
    """
    Compute detailed CPL distribution stats for one side.
    
    Returns a dict with:
    - mean        : average CPL
    - median      : median CPL  
    - stdev       : standard deviation
    - variance    : variance
    - cv          : coefficient of variation (stdev/mean) — key cheating signal
    - skewness    : are mistakes randomly distributed or suspiciously even?
    - percentiles : 25th, 75th, 90th percentile CPL
    - blunder_pct : % of moves with CPL > 150
    - mistake_pct : % of moves with CPL > 50
    - perfect_pct : % of moves with CPL < 5
    - max_cpl     : worst single move
    - suspicious  : True if distribution looks engine-like
    """
    losses = [m.centipawn_loss for m in moves 
              if m.centipawn_loss is not None and not m.forced]
    
    if len(losses) < 5:
        return {"error": "not enough moves"}
    
    mean = statistics.mean(losses)
    median = statistics.median(losses)
    stdev = statistics.stdev(losses) if len(losses) > 1 else 0
    variance = statistics.variance(losses) if len(losses) > 1 else 0
    cv = stdev / mean if mean > 0 else 0
    
    # Skewness — human play is right-skewed (mostly small losses, occasional big ones)
    # Engine play is more symmetric and tight
    n = len(losses)
    if stdev > 0 and n >= 3:
        skewness = (n / ((n-1) * (n-2))) * sum(
            ((x - mean) / stdev) ** 3 for x in losses
        )
    else:
        skewness = 0
    
    # Percentiles
    sorted_losses = sorted(losses)
    p25 = sorted_losses[int(n * 0.25)]
    p75 = sorted_losses[int(n * 0.75)]
    p90 = sorted_losses[int(n * 0.90)]
    
    blunder_pct = sum(1 for x in losses if x > 150) / n * 100
    mistake_pct = sum(1 for x in losses if x > 50) / n * 100
    perfect_pct = sum(1 for x in losses if x < 5) / n * 100
    
    # Suspicious if:
    # - CV is very low (moves are unnaturally consistent)
    # - perfect_pct is very high (too many engine-perfect moves)
    # - skewness is near 0 (no random human blunders)
    suspicious = (
        cv < 0.8 and
        perfect_pct > 60 and
        blunder_pct < 3
    )
    
    return {
        "mean":        round(mean, 2),
        "median":      round(median, 2),
        "stdev":       round(stdev, 2),
        "variance":    round(variance, 2),
        "cv":          round(cv, 2),
        "skewness":    round(skewness, 2),
        "p25":         round(p25, 2),
        "p75":         round(p75, 2),
        "p90":         round(p90, 2),
        "blunder_pct": round(blunder_pct, 2),
        "mistake_pct": round(mistake_pct, 2),
        "perfect_pct": round(perfect_pct, 2),
        "max_cpl":     round(max(losses), 2),
        "move_count":  n,
        "suspicious":  suspicious,
    }


def cpl_distribution_score(dist: dict) -> tuple[float, str]:
    """
    Convert CPL distribution stats into a 0-100 suspicion score.
    Returns (score, explanation).
    """
    if "error" in dist:
        return 0.0, "not enough data"
    
    score = 0.0
    reasons = []
    
    # Low CV = unnaturally consistent mistakes
    cv = dist["cv"]
    if cv < 0.3:
        score += 40
        reasons.append(f"very low variance (CV={cv})")
    elif cv < 0.6:
        score += 20
        reasons.append(f"low variance (CV={cv})")
    elif cv < 0.8:
        score += 10
        reasons.append(f"slightly low variance (CV={cv})")
    
    # High perfect move percentage
    perfect = dist["perfect_pct"]
    if perfect > 80:
        score += 35
        reasons.append(f"{perfect}% perfect moves")
    elif perfect > 65:
        score += 20
        reasons.append(f"{perfect}% perfect moves")
    elif perfect > 50:
        score += 10
        reasons.append(f"{perfect}% perfect moves")
    
    # No blunders
    blunders = dist["blunder_pct"]
    if blunders == 0:
        score += 15
        reasons.append("zero blunders")
    elif blunders < 2:
        score += 8
        reasons.append(f"very few blunders ({blunders}%)")
    
    # Low skewness (humans should have right-skewed CPL distribution)
    skew = dist["skewness"]
    if abs(skew) < 0.5 and dist["mean"] < 20:
        score += 10
        reasons.append(f"unnaturally symmetric mistake distribution")
    
    score = min(score, 100.0)
    explanation = ", ".join(reasons) if reasons else "normal distribution"
    
    return round(score, 1), explanation
