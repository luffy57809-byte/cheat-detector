import requests
import chess
import chess.pgn
import io

def get_out_of_book_ply(pgn_text: str, min_games: int = 5) -> int:
    """
    Find the ply where the game leaves opening theory.
    Uses Lichess masters database to check each position.
    Returns the ply number after which moves are out of book.
    """
    try:
        game = chess.pgn.read_game(io.StringIO(pgn_text))
        board = game.board()
        last_book_ply = 0

        for ply, move in enumerate(game.mainline_moves(), start=1):
            if ply > 20:
                break

            fen = board.fen()
            try:
                resp = requests.get(
                    "https://explorer.lichess.ovh/masters",
                    params={"fen": fen},
                    timeout=4
                )
                if resp.status_code == 200:
                    data = resp.json()
                    total = data.get("white", 0) + data.get("draws", 0) + data.get("black", 0)
                    if total >= min_games:
                        last_book_ply = ply
                    else:
                        board.push(move)
                        break
            except:
                board.push(move)
                break

            board.push(move)

        return last_book_ply

    except Exception as e:
        print(f"Opening detection error: {e}")
        return 0


def filter_book_moves(moves: list, out_of_book_ply: int) -> list:
    """
    Remove opening book moves from a move list.
    Only returns moves after the book ends.
    """
    return [m for m in moves if m.ply > out_of_book_ply]
