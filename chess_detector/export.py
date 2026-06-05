import json
import csv
import os
from chess_detector.database import get_connection

def export_json(username: str = None, output_path: str = "reports.json"):
    """Export all reports (or for one player) to JSON."""
    conn = get_connection()
    if username:
        rows = conn.execute(
            "SELECT * FROM reports WHERE username = ? ORDER BY created_at DESC",
            (username.lower(),)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM reports ORDER BY created_at DESC"
        ).fetchall()
    conn.close()

    data = []
    for r in rows:
        row = dict(r)
        row["features"] = json.loads(row["features"] or "[]")
        row["flagged_moves"] = json.loads(row["flagged_moves"] or "[]")
        data.append(row)

    open(output_path, "w").write(json.dumps(data, indent=2))
    print(f"Exported {len(data)} report(s) to {output_path}")
    return data


def export_csv(username: str = None, output_path: str = "reports.csv"):
    """Export summary reports to CSV — one row per game."""
    conn = get_connection()
    if username:
        rows = conn.execute(
            "SELECT * FROM reports WHERE username = ? ORDER BY created_at DESC",
            (username.lower(),)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM reports ORDER BY created_at DESC"
        ).fetchall()
    conn.close()

    if not rows:
        print("No reports found.")
        return

    with open(output_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "game_id", "username", "platform", "color",
            "overall_score", "verdict", "flagged_moves", "created_at"
        ])
        for r in rows:
            row = dict(r)
            writer.writerow([
                row["game_id"], row["username"], row["platform"],
                row["color"], row["overall_score"], row["verdict"],
                row["flagged_moves"], row["created_at"]
            ])

    print(f"Exported {len(rows)} report(s) to {output_path}")


def export_player_summary(username: str, output_path: str = None):
    """Export a full player summary including per-feature averages."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM reports WHERE username = ? ORDER BY created_at DESC",
        (username.lower(),)
    ).fetchall()
    conn.close()

    if not rows:
        print(f"No reports found for {username}")
        return None

    reports = [dict(r) for r in rows]
    scores = [r["overall_score"] for r in reports]
    verdicts = [r["verdict"] for r in reports]

    # Aggregate feature scores across all games
    feature_totals = {}
    feature_counts = {}
    for r in reports:
        features = json.loads(r["features"] or "[]")
        for f in features:
            name = f["name"]
            feature_totals[name] = feature_totals.get(name, 0) + f["score"]
            feature_counts[name] = feature_counts.get(name, 0) + 1

    feature_averages = {
        name: round(feature_totals[name] / feature_counts[name], 2)
        for name in feature_totals
    }

    summary = {
        "username": username,
        "games_analyzed": len(reports),
        "avg_score": round(sum(scores) / len(scores), 2),
        "max_score": round(max(scores), 2),
        "min_score": round(min(scores), 2),
        "clean_games": verdicts.count("clean"),
        "suspicious_games": verdicts.count("suspicious"),
        "cheating_games": verdicts.count("likely cheating"),
        "overall_verdict": _overall_verdict(sum(scores) / len(scores)),
        "feature_averages": feature_averages,
        "games": reports,
    }

    path = output_path or f"{username}_summary.json"
    open(path, "w").write(json.dumps(summary, indent=2))
    print(f"Player summary exported to {path}")
    return summary


def _overall_verdict(avg_score: float) -> str:
    if avg_score >= 60: return "likely cheating"
    if avg_score >= 30: return "suspicious"
    return "clean"
