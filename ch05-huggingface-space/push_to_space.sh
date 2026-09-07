#!/usr/bin/env bash
# push_to_space.sh — deploy this app.py to a public Hugging Face Space.
#
# Prerequisites (one time):
#   1. A free account at https://huggingface.co
#   2. A write token: https://huggingface.co/settings/tokens  (role: "write")
#   3. pip install huggingface_hub    (gives you the `hf` / `huggingface-cli` command)
#
# Usage:
#   export HF_TOKEN="hf_..."                 # your write token -- DEPLOY ONLY
#   ./push_to_space.sh <your-username> <space-name>
#
# Example:
#   ./push_to_space.sh napoleon zero-shot-classifier
#
# After it finishes, your app is live at:
#   https://huggingface.co/spaces/<your-username>/<space-name>
#
# IMPORTANT -- use two different tokens:
#   This script needs WRITE, because it creates the Space and uploads files.
#   The running app does NOT: it only calls Inference Providers. Do not paste
#   this write token into the Space secret. A public Space holding a write token
#   is a public page holding a credential that can push to all of your repos.
#   For the Space secret, create a FINE-GRAINED token with inference permission
#   only. See: https://huggingface.co/docs/hub/en/security-tokens
set -euo pipefail

USERNAME="${1:-}"
SPACE_NAME="${2:-}"

if [[ -z "$USERNAME" || -z "$SPACE_NAME" ]]; then
  echo "Usage: ./push_to_space.sh <your-username> <space-name>" >&2
  exit 2
fi

if [[ -z "${HF_TOKEN:-}" ]]; then
  echo "Set HF_TOKEN to a write token first: https://huggingface.co/settings/tokens" >&2
  exit 1
fi

REPO_ID="${USERNAME}/${SPACE_NAME}"
echo ">>> Creating (or reusing) Gradio Space: ${REPO_ID}"

# Create the Space repo if it doesn't already exist (Gradio SDK).
python3 - "$REPO_ID" <<'PY'
import sys, os
from huggingface_hub import create_repo
repo_id = sys.argv[1]
create_repo(repo_id, repo_type="space", space_sdk="gradio",
            token=os.environ["HF_TOKEN"], exist_ok=True)
print(f"    ok: {repo_id}")
PY

echo ">>> Uploading app.py + requirements.txt"
python3 - "$REPO_ID" <<'PY'
import sys, os
from huggingface_hub import HfApi
repo_id = sys.argv[1]
api = HfApi(token=os.environ["HF_TOKEN"])
for fname in ("app.py", "requirements.txt"):
    api.upload_file(path_or_fileobj=fname, path_in_repo=fname,
                    repo_id=repo_id, repo_type="space")
    print(f"    uploaded: {fname}")
PY

echo ""
echo ">>> Done. Your Space is building now — it will be live shortly at:"
echo "    https://huggingface.co/spaces/${REPO_ID}"
echo ""
echo ">>> One more step: Settings → Variables and secrets → add a secret HF_TOKEN"
echo "    so the app can call Inference Providers."
echo "    Use a FINE-GRAINED, inference-only token there -- NOT the write token"
echo "    you just deployed with. https://huggingface.co/docs/hub/en/security-tokens"
