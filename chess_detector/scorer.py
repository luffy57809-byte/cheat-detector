from dataclasses import dataclass, field
from typing import Optional
import math

# ------------------------------------------------
# Expected values by rating and time control
# ------------------------------------------------

EXPECTED_ACPL = {
    "bullet":    {1000: 80, 1200: 55, 1400: 45, 1600: 35, 1800: 25, 2000: 18, 2200: 12, 2400: 8},
    "blitz":     {1000: 70, 1200: 48, 1400: 38, 1600: 28, 1800: 20, 2000: 14, 2200: 9,  2400: 6},
    "rapid":     {1000: 60, 1200: 40, 1400: 30, 1600: 22, 1800: 15, 2000: 10, 2200: 7,  2400: 4},
    "classical": {1000: 50, 1200: 32, 1400: 24, 1600: 18, 1800: 12, 2000: 8,  2200: 5,  2400: 3},
}

EXPECTED_TOP1 = {
    1000: 32, 1200: 40, 1400: 48, 1600: 56, 1800: 63, 2000: 70, 2200: 76, 2400: 82
}

# ------------------------------------------------
# Data structures
# ------------------------------------------------

@dataclass
class FeatureScore:
    name: str
    raw_value: float
    score: float        # 0-100 suspicion contribution
    weight: float
    note: str = ""

@dataclass
class SuspicionReport:
    game_id: str
    username: str
    color: str
    overall_score: float
    verdict: str
    features: list = field(default_factory=list)
    flagged_moves: list = field(default_factory=list)

    def summary(self):
        lines = [
            f"",
            f"  Game     : {self.game_id}",
            f"  Player   : {self.username} ({self.color})",
            f"  Score    : {self.overall_score:.1f}/100",
            f"  Verdict  : {self.verdict.upper()}",
            f"",
            f"  {'Feature':<30} {'Score':>6}   Note",
            f"  {'-'*70}",
        ]
        for f in self.features:
            bar = chr(9608) * int(f.score / 10)
            lines.append(f"  {f.name:<30} {f.score:>5.1f}   {f.note}")
        if self.flagged_moves:
            lines.append(f"")
            lines.append(f"  Flagged moves (ply): {self.flagged_moves}")
        return "\n".join(lines)


# ------------------------------------------------
# Scorer
# ------------------------------------------------

class SuspicionScorer:

    def score(self, analysis, username: str, color: str, rating: Optional[int] = None, pgn_text: str = None) -> SuspicionReport:
        from chess_detector.opening import get_out_of_book_ply, filter_book_moves
        moves = [m for m in analysis.moves if m.color == color]
        
        # Remove opening book moves from analysis
        if pgn_text:
            print(f"  Detecting opening book moves...")
            out_of_book_ply = get_out_of_book_ply(pgn_text)
            if out_of_book_ply > 0:
                original_count = len(moves)
                moves = filter_book_moves(moves, out_of_book_ply)
                print(f"  Excluded {original_count - len(moves)} book moves (first {out_of_book_ply} plies)")
        features = []

        # 1. ACPL feature
        features.append(self._acpl_feature(analysis, color, rating, analysis.time_control))

        # 2. Top-1 match rate
        features.append(self._top1_feature(analysis, color, rating))

        # 3. Top-3 match rate
        features.append(self._top3_feature(analysis, color))

        # 4. Critical move accuracy
        features.append(self._critical_feature(moves))

        # 5. Blunder absence
        features.append(self._blunder_feature(moves))

        # 6. Move time consistency (if clock data exists)
        time_feature = self._time_feature(moves)
        if time_feature:
            features.append(time_feature)

        # 7. CPL distribution
        features.append(self._cpl_distribution_feature(moves))

        # Weighted average
        total_weight = sum(f.weight for f in features)
        overall = sum(f.score * f.weight for f in features) / total_weight
        overall = round(min(overall, 100.0), 1)

        return SuspicionReport(
            game_id=analysis.game_id,
            username=username,
            color=color,
            overall_score=overall,
            verdict=self._verdict(overall),
            features=features,
            flagged_moves=self._flag_moves(moves),
        )

    # ------------------------------------------------
    # Individual features
    # ------------------------------------------------

    def _acpl_feature(self, analysis, color, rating, time_control):
        acpl = getattr(analysis, f"{color}_acpl")
        if acpl is None:
            return FeatureScore("Avg centipawn loss", 0, 0, 2.5, "no data")
        tc = self._tc_bucket(time_control)
        expected = self._interp(EXPECTED_ACPL.get(tc, EXPECTED_ACPL["blitz"]), rating or 1500)
        # How many times better than expected?
        ratio = expected / max(acpl, 0.1)
        score = min(self._sigmoid(ratio, midpoint=2.5, steepness=2.5) * 100, 100)
        note = f"ACPL={acpl:.1f}  (expected ~{expected:.0f} for this rating/TC)"
        return FeatureScore("Avg centipawn loss", acpl, round(score, 1), 2.5, note)

    def _top1_feature(self, analysis, color, rating):
        top1 = getattr(analysis, f"{color}_top1_pct") or 0.0
        expected = self._interp(EXPECTED_TOP1, rating or 1500)
        excess = max(top1 - expected, 0)
        score = min(excess * 1.8, 100)
        note = f"Top-1={top1:.1f}%  (expected ~{expected:.0f}% for rating)"
        return FeatureScore("Engine top-1 match", top1, round(score, 1), 2.5, note)

    def _top3_feature(self, analysis, color):
        top3 = getattr(analysis, f"{color}_top3_pct") or 0.0
        score = max(0, (top3 - 88) * 2.5)
        score = min(score, 100)
        note = f"Top-3={top3:.1f}%  (GMs average ~88-92%)"
        return FeatureScore("Engine top-3 match", top3, round(score, 1), 1.5, note)

    def _critical_feature(self, moves):
        balanced = [m for m in moves if m.eval_before is not None and abs(m.eval_before) < 150]
        perfect  = [m for m in balanced if m.centipawn_loss is not None and m.centipawn_loss < 10]
        if len(balanced) < 3:
            return FeatureScore("Critical position accuracy", 0, 0, 1.0, "too few balanced positions")
        ratio = len(perfect) / len(balanced) * 100
        score = max(0, (ratio - 65) * 1.8)
        score = min(score, 100)
        note = f"Engine-perfect in {ratio:.0f}% of balanced positions"
        return FeatureScore("Critical position accuracy", ratio, round(score, 1), 2.0, note)

    def _blunder_feature(self, moves):
        total = len(moves)
        if total == 0:
            return FeatureScore("Blunder absence", 0, 0, 1.0, "no data")
        blunders = [m for m in moves if m.centipawn_loss is not None and m.centipawn_loss > 150]
        rate = len(blunders) / total * 100
        score = max(0, 50 - rate * 8)
        note = f"{len(blunders)} blunders in {total} moves ({rate:.1f}%)"
        return FeatureScore("Blunder absence", rate, round(score, 1), 1.0, note)

    def _time_feature(self, moves):
        import statistics
        times = [m.think_time_ms for m in moves if m.think_time_ms is not None and m.think_time_ms > 0]
        if len(times) < 8:
            return None
        mean_t = statistics.mean(times)
        if mean_t == 0:
            return None
        cv = statistics.stdev(times) / mean_t
        score = max(0, (0.5 - cv) * 200)
        score = min(score, 100)
        note = f"Time CV={cv:.2f}  (humans ~0.8-2.0, engines ~0.1-0.3)"
        return FeatureScore("Move time consistency", cv, round(score, 1), 1.5, note)

    def _flag_moves(self, moves):
        flagged = []
        for m in moves:
            critical = m.eval_before is not None and abs(m.eval_before) < 100
            perfect  = m.is_top1 and (m.centipawn_loss or 0) < 5
            fast     = m.think_time_ms is not None and m.think_time_ms < 3000
            if critical and perfect and fast:
                flagged.append(m.ply)
        return flagged

    # ------------------------------------------------
    # Helpers
    # ------------------------------------------------

    def _tc_bucket(self, tc: str) -> str:
        try:
            base = int(str(tc).split("+")[0])
        except:
            return "blitz"
        if base < 180:   return "bullet"
        if base < 600:   return "blitz"
        if base < 1800:  return "rapid"
        return "classical"

    def _interp(self, table: dict, rating: int) -> float:
        keys = sorted(table.keys())
        if rating <= keys[0]:  return table[keys[0]]
        if rating >= keys[-1]: return table[keys[-1]]
        for i in range(len(keys) - 1):
            if keys[i] <= rating < keys[i+1]:
                t = (rating - keys[i]) / (keys[i+1] - keys[i])
                return table[keys[i]] + t * (table[keys[i+1]] - table[keys[i]])
        return table[keys[0]]

    def _sigmoid(self, x, midpoint=1.0, steepness=2.0) -> float:
        return 1 / (1 + math.exp(-steepness * (x - midpoint)))


    def _cpl_distribution_feature(self, moves):
        from chess_detector.cpl_distribution import compute_cpl_distribution, cpl_distribution_score
        dist = compute_cpl_distribution(moves)
        score, explanation = cpl_distribution_score(dist)
        note = explanation
        if "error" not in dist:
            note += f" | CV={dist.get('cv','?')} perfect={dist.get('perfect_pct','?')}%"
        return FeatureScore("CPL distribution", score, score, 2.0, note)
    def _verdict(self, score: float) -> str:
        if score < 30:  return "clean"
        if score < 60:  return "suspicious"
        return "likely cheating"
