import chess
import chess.engine
import chess.pgn
import io
import re
from dataclasses import dataclass, field
from typing import Optional

STOCKFISH_PATH = "/usr/games/stockfish"

@dataclass
class MoveAnalysis:
    ply: int
    move_uci: str
    move_san: str
    color: str
    eval_before: Optional[float]
    eval_after: Optional[float]
    centipawn_loss: Optional[float]
    engine_top_moves: list
    is_top1: bool
    is_top3: bool
    think_time_ms: Optional[int]
    forced: bool

@dataclass
class GameAnalysis:
    game_id: str
    white_username: str
    black_username: str
    time_control: str
    date: str
    result: str
    moves: list = field(default_factory=list)
    white_acpl: Optional[float] = None
    black_acpl: Optional[float] = None
    white_top1_pct: Optional[float] = None
    black_top1_pct: Optional[float] = None
    white_top3_pct: Optional[float] = None
    black_top3_pct: Optional[float] = None

    def compute_stats(self):
        for color in ("white", "black"):
            moves = [m for m in self.moves if m.color == color]
            losses = [m.centipawn_loss for m in moves if m.centipawn_loss is not None]
            if losses:
                setattr(self, f"{color}_acpl", round(sum(losses) / len(losses), 2))
            if moves:
                setattr(self, f"{color}_top1_pct", round(100.0 * sum(1 for m in moves if m.is_top1) / len(moves), 2))
                setattr(self, f"{color}_top3_pct", round(100.0 * sum(1 for m in moves if m.is_top3) / len(moves), 2))

def analyze_pgn(pgn_text: str, depth: int = 15) -> GameAnalysis:
    # Pre-check: make sure the PGN parses cleanly
    import io as _io
    test_game = chess.pgn.read_game(_io.StringIO(pgn_text))
    if test_game is None:
        raise ValueError("Could not parse PGN")
    # Check for non-standard notation by walking moves
    test_board = test_game.board()
    for move in test_game.mainline_moves():
        test_board.push(move)

    game = chess.pgn.read_game(io.StringIO(pgn_text))
    headers = game.headers
    # Generate a unique game ID
    site = headers.get("Site", "unknown")
    raw_id = site.split("/")[-1]
    if not raw_id or raw_id == "Chess.com":
        # Chess.com doesn't put game ID in Site — use White+Black+Date+Round
        white = headers.get("White", "?")
        black = headers.get("Black", "?")
        date  = headers.get("Date", "?")
        rnd   = headers.get("Round", "?")
        raw_id = f"{white}_{black}_{date}_{rnd}".replace(" ", "_").replace(".", "")
    analysis = GameAnalysis(
        game_id=raw_id,
        white_username=headers.get("White", "?"),
        black_username=headers.get("Black", "?"),
        time_control=headers.get("TimeControl", "?"),
        date=headers.get("Date", "?"),
        result=headers.get("Result", "*"),
    )
    with chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH) as engine:
        engine.configure({"Hash": 128, "Threads": 1})
        board = game.board()
        for ply, (move, node) in enumerate(zip(game.mainline_moves(), game.mainline()), start=1):
            color = "white" if board.turn == chess.WHITE else "black"
            info_before = engine.analyse(board, chess.engine.Limit(depth=depth), multipv=3)
            eval_before = _get_cp(info_before[0].get("score"))
            top_moves = [e.get("pv")[0].uci() for e in info_before if e.get("pv")]
            played_san = board.san(move)
            played_uci = move.uci()
            board.push(move)
            info_after = engine.analyse(board, chess.engine.Limit(depth=depth), multipv=1)
            raw_after = _get_cp(info_after[0].get("score") if isinstance(info_after, list) else info_after.get("score"))
            eval_after = -raw_after if raw_after is not None else None
            cpl = max(eval_before - eval_after, 0) if eval_before is not None and eval_after is not None else None
            board.pop()
            forced = board.legal_moves.count() == 1
            board.push(move)
            analysis.moves.append(MoveAnalysis(
                ply=ply, move_uci=played_uci, move_san=played_san, color=color,
                eval_before=eval_before, eval_after=eval_after, centipawn_loss=cpl,
                engine_top_moves=top_moves,
                is_top1=len(top_moves) > 0 and played_uci == top_moves[0],
                is_top3=played_uci in top_moves[:3],
                think_time_ms=_parse_clock(node), forced=forced,
            ))
    analysis.compute_stats()
    return analysis

def _get_cp(score_obj):
    if score_obj is None:
        return None
    try:
        pov = score_obj.relative
        if pov.is_mate():
            return 10000.0 if pov.mate() > 0 else -10000.0
        return float(pov.score())
    except:
        return None

def _parse_clock(node):
    comment = node.comment or ""
    match = re.search(r"\[%clk\s+(\d+):(\d+):(\d+(?:\.\d+)?)\]", comment)
    if match:
        h, m, s = match.groups()
        return int(h) * 3600000 + int(m) * 60000 + int(float(s) * 1000)
    return None
