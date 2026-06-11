from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.responses import JSONResponse
from collections import defaultdict
import time
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import tempfile, os

from chess_detector.pgn_upload import analyze_pgn_file
from chess_detector.export import export_player_summary
from chess_detector.database import init_db

app = FastAPI()

# Simple in-memory rate limiter
request_counts = defaultdict(list)
RATE_LIMIT = 10  # max requests
RATE_WINDOW = 60  # per 60 seconds

def is_rate_limited(ip: str) -> bool:
    now = time.time()
    request_counts[ip] = [t for t in request_counts[ip] if now - t < RATE_WINDOW]
    if len(request_counts[ip]) >= RATE_LIMIT:
        return True
    request_counts[ip].append(now)
    return False

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()

@app.post("/analyze")
async def analyze(
    request: Request,
    pgn: str = Form(None),
    file: UploadFile = File(None),
    username: str = Form(None),
    rating: int = Form(None),
    depth: int = Form(15),
    color: str = Form(None),
):
    ip = request.client.host
    if is_rate_limited(ip):
        return JSONResponse({"error": "Too many requests. Please wait a minute."}, status_code=429)

    if file:
        contents = await file.read()
        pgn_text = contents.decode("utf-8", errors="replace")
    elif pgn:
        pgn_text = pgn
    else:
        return JSONResponse({"error": "No PGN provided"}, status_code=400)

    with tempfile.NamedTemporaryFile(suffix=".pgn", mode="w", delete=False) as f:
        f.write(pgn_text)
        tmp_path = f.name

    try:
        reports = analyze_pgn_file(tmp_path, username=username, rating=rating, depth=depth)
    finally:
        os.unlink(tmp_path)

    if not reports:
        return JSONResponse({"error": "No games could be analyzed"}, status_code=422)

    avg = sum(r.overall_score for r in reports) / len(reports)
    return {
        "username": username or reports[0].username,
        "games_analyzed": len(reports),
        "avg_score": round(avg, 2),
        "max_score": round(max(r.overall_score for r in reports), 1),
        "min_score": round(min(r.overall_score for r in reports), 1),
        "clean_games":      sum(1 for r in reports if r.verdict == "clean"),
        "suspicious_games": sum(1 for r in reports if r.verdict == "suspicious"),
        "cheating_games":   sum(1 for r in reports if r.verdict == "likely cheating"),
        "overall_verdict":  "likely cheating" if avg >= 60 else "suspicious" if avg >= 30 else "clean",
        "feature_averages": _avg_features(reports),
        "games": [
            {
                "game_id": r.game_id,
                "username": r.username,
                "color": r.color,
                "overall_score": r.overall_score,
                "verdict": r.verdict,
                "flagged_moves": r.flagged_moves,
                "features": [{"name": f.name, "score": f.score, "note": f.note} for f in r.features],
            }
            for r in reports
        ],
    }

def _avg_features(reports):
    totals, counts = {}, {}
    for r in reports:
        for f in r.features:
            totals[f.name] = totals.get(f.name, 0) + f.score
            counts[f.name] = counts.get(f.name, 0) + 1
    return {name: round(totals[name] / counts[name], 2) for name in totals}

@app.get("/health")
def health():
    return {"status": "ok"}

from chess_detector.fetcher import fetch_games
from chess_detector.batch import batch_analyze

@app.post("/analyze-player")
async def analyze_player(
    username: str = Form(...),
    platform: str = Form("auto"),
    max_games: int = Form(5),
    depth: int = Form(15),
):
    try:
        reports = batch_analyze(username, platform=platform, max_games=max_games)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

    if not reports:
        return JSONResponse({"error": "No games could be analyzed"}, status_code=422)

    avg = sum(r.overall_score for r in reports) / len(reports)
    return {
        "username": username,
        "games_analyzed": len(reports),
        "avg_score": round(avg, 2),
        "max_score": round(max(r.overall_score for r in reports), 1),
        "min_score": round(min(r.overall_score for r in reports), 1),
        "clean_games":      sum(1 for r in reports if r.verdict == "clean"),
        "suspicious_games": sum(1 for r in reports if r.verdict == "suspicious"),
        "cheating_games":   sum(1 for r in reports if r.verdict == "likely cheating"),
        "overall_verdict":  "likely cheating" if avg >= 60 else "suspicious" if avg >= 30 else "clean",
        "feature_averages": _avg_features(reports),
        "games": [
            {
                "game_id": r.game_id,
                "username": r.username,
                "color": r.color,
                "overall_score": r.overall_score,
                "verdict": r.verdict,
                "flagged_moves": r.flagged_moves,
                "features": [{"name": f.name, "score": f.score, "note": f.note} for f in r.features],
            }
            for r in reports
        ],
    }
