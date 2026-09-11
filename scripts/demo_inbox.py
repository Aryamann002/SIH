"""Local trusted-verifier simulation: show an action's OTP only to the local operator."""
import argparse
import json
import sys
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.config import settings


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action_id", type=UUID)
    args = parser.parse_args()
    request = Request(f"http://127.0.0.1:8000/api/v1/demo/inbox/{args.action_id}",
                      headers={"X-Demo-Verifier-Key": settings.DEMO_VERIFIER_KEY})
    try:
        with urlopen(request, timeout=5) as response:
            print(json.dumps(json.load(response), indent=2))
    except HTTPError as exc:
        parser.exit(1, "No pending message, or verifier credentials are unavailable.\n")
