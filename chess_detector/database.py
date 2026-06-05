import sqlite3
import json
import os
from datetime import datetime
from typing import Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "cheat_detector.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Create all tables if they dont exist."""
    conn = get_connection()
    c = conn.cursor()

    c.executescript("""
        CREATE TABLE IF NOT EXISTS players (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            username    TEXT NOT NULL,
            platform    TEXT NOT NULL,
            rating      INTEGER,
            created_at  TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(username, platform)
        );

        CREATE TABLE IF NOT EXISTS games (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id         TEXT NOT NULL,
            platform        TEXT NOT NULL,
            white_username  TEXT,
            black_username  TEXT,
            time_control    TEXT,
            date            TEXT,
            result          TEXT,
            pgn             TEXT,
            created_at      TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(game_id, platform)
        );

        CREATE TABLE IF NOT EXISTS move_analysis (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id     TEXT NOT NULL,
            ply         INTEGER,
            move_san    TEXT,
            move_uci    TEXT,
            color       TEXT,
            eval_before REAL,
            eval_after  REAL,
            cpl         REAL,
            is_top1     INTEGER,
            is_top3     INTEGER,
            think_ms    INTEGER,
            forced      INTEGER
        );

        CREATE TABLE IF NOT EXISTS reports (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id         TEXT NOT NULL,
            username        TEXT NOT NULL,
            platform        TEXT,
            color           TEXT,
            overall_score   REAL,
            verdict         TEXT,
            features        TEXT,
            flagged_moves   TEXT,
            created_at      TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """)

    conn.commit()
    conn.close()
    print("Database initialized!")


# ------------------------------------------------
# Save functions
# ------------------------------------------------

def save_player(username: str, platform: str, rating: Optional[int] = None):
    conn = get_connection()
    conn.execute("""
        INSERT INTO players (username, platform, rating)
        VALUES (?, ?, ?)
        ON CONFLICT(username, platform) DO UPDATE SET rating=excluded.rating
    """, (username.lower(), platform, rating))
    conn.commit()
    conn.close()


def save_game(analysis, pgn: str, platform: str):
    """Save a GameAnalysis object to the database."""
    conn = get_connection()
    
    # Save game
    try:
        conn.execute("""
            INSERT OR IGNORE INTO games 
            (game_id, platform, white_username, black_username, time_control, date, result, pgn)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            sanitize(analysis.game_id), sanitize(platform),
            sanitize(analysis.white_username), sanitize(analysis.black_username),
            sanitize(analysis.time_control), sanitize(analysis.date),
            sanitize(analysis.result), sanitize(pgn)
        ))
    except Exception as e:
        print(f"Warning saving game: {e}")

    # Save moves
    for m in analysis.moves:
        conn.execute("""
            INSERT INTO move_analysis
            (game_id, ply, move_san, move_uci, color, eval_before, eval_after, cpl, is_top1, is_top3, think_ms, forced)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            analysis.game_id, m.ply, m.move_san, m.move_uci,
            m.color, m.eval_before, m.eval_after, m.centipawn_loss,
            int(m.is_top1), int(m.is_top3), m.think_time_ms, int(m.forced)
        ))

    conn.commit()
    conn.close()


def sanitize(text):
    """Remove problematic characters from text before saving."""
    if text is None:
        return None
    return str(text).replace("\x00", "").encode("utf-8", "ignore").decode("utf-8")

def save_report(report, platform: str = "unknown"):
    """Save a SuspicionReport to the database."""
    conn = get_connection()
    conn.execute("""
        INSERT INTO reports
        (game_id, username, platform, color, overall_score, verdict, features, flagged_moves)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        report.game_id,
        report.username.lower(),
        platform,
        report.color,
        report.overall_score,
        report.verdict,
        json.dumps([{"name": f.name, "score": f.score, "note": f.note} for f in report.features]),
        json.dumps(report.flagged_moves),
    ))
    conn.commit()
    conn.close()


# ------------------------------------------------
# Query functions
# ------------------------------------------------

def get_player_reports(username: str) -> list:
    """Get all reports for a player across all games."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT * FROM reports
        WHERE username = ?
        ORDER BY created_at DESC
    """, (username.lower(),)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_player_average_score(username: str) -> Optional[float]:
    """Get a players average suspicion score across all analyzed games."""
    conn = get_connection()
    row = conn.execute("""
        SELECT AVG(overall_score) as avg_score, COUNT(*) as game_count
        FROM reports WHERE username = ?
    """, (username.lower(),)).fetchone()
    conn.close()
    if row and row["game_count"] > 0:
        return {"avg_score": round(row["avg_score"], 1), "game_count": row["game_count"]}
    return None


def is_game_analyzed(game_id: str) -> bool:
    """Check if a game has already been analyzed — avoids duplicate work."""
    conn = get_connection()
    row = conn.execute("""
        SELECT id FROM reports WHERE game_id = ?
    """, (game_id,)).fetchone()
    conn.close()
    return row is not None


def get_flagged_players(min_score: float = 60.0, min_games: int = 2) -> list:
    """Get all players whose average score exceeds the threshold."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT username, platform, AVG(overall_score) as avg_score, COUNT(*) as game_count
        FROM reports
        GROUP BY username, platform
        HAVING avg_score >= ? AND game_count >= ?
        ORDER BY avg_score DESC
    """, (min_score, min_games)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_game_moves(game_id: str) -> list:
    """Get all move analysis data for a specific game."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT * FROM move_analysis WHERE game_id = ?
        ORDER BY ply ASC
    """, (game_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]
