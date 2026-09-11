"""Create local secrets once. Keep the verifier key out of the operator interface."""
import json
from pathlib import Path
import secrets
import subprocess
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]


def configure():
    path = ROOT / ".env"
    if path.exists():
        print("Existing .env preserved. Run scripts/demo_inbox.py to view a verification message.")
        return
    password = secrets.token_urlsafe(24)
    # Preserve credentials for this project's existing local database volume.
    try:
        result = subprocess.run(["docker", "inspect", "vigilvoice_db"], capture_output=True, text=True, check=True)
        container = json.loads(result.stdout)[0]
        owner = container["Config"]["Labels"].get("com.docker.compose.project.working_dir", "")
        if Path(owner).resolve() == ROOT:
            env = dict(item.split("=", 1) for item in container["Config"]["Env"] if "=" in item)
            password = env["POSTGRES_PASSWORD"]
    except (OSError, subprocess.CalledProcessError, KeyError, ValueError):
        pass
    values = {"POSTGRES_PASSWORD": password,
              "DATABASE_URL": f"postgresql+asyncpg://vigilvoice:{quote(password, safe='')}@localhost:5433/vigilvoice",
              "VERIFICATION_SECRET": secrets.token_urlsafe(32), "DEMO_VERIFIER_KEY": secrets.token_urlsafe(32)}
    path.write_text("\n".join(f"{key}={value}" for key, value in values.items()) + "\n", encoding="utf-8")
    print("Created ignored .env with local credentials. No secrets were printed.")


if __name__ == "__main__":
    configure()
