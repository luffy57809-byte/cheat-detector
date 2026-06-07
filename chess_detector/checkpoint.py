import os
import json
from pathlib import Path

CHECKPOINT_DIR = "/tmp/.checkpoints"

def save_checkpoint(username: str, platform: str, completed_game_ids: list, remaining_pgns: list):
    """Save progress so we can resume if something crashes."""
    os.makedirs(CHECKPOINT_DIR, exist_ok=True)
    checkpoint = {
        "username": username,
        "platform": platform,
        "completed_game_ids": completed_game_ids,
        "remaining_pgns": remaining_pgns,
    }
    path = _checkpoint_path(username, platform)
    open(path, "w").write(json.dumps(checkpoint))


def load_checkpoint(username: str, platform: str) -> dict:
    """Load a saved checkpoint if it exists."""
    path = _checkpoint_path(username, platform)
    if os.path.exists(path):
        try:
            return json.loads(open(path).read())
        except:
            return None
    return None


def clear_checkpoint(username: str, platform: str):
    """Delete checkpoint after successful completion."""
    path = _checkpoint_path(username, platform)
    if os.path.exists(path):
        os.remove(path)


def _checkpoint_path(username: str, platform: str) -> str:
    return os.path.join(CHECKPOINT_DIR, f"{username}_{platform}.json")
