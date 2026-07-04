#!/usr/bin/env bash
# deploy_huggingface.sh — publish the generated Hugging Face Space artifacts.
#
# The Chapter 9 packager writes a Hugging Face artifact set into:
#     <out>/huggingface/README.md   (with the Space YAML header)
#     <out>/huggingface/app.py      (a Gradio scaffold that boots green)
#
# This script creates a Gradio Space and uploads those two files. This is the
# same create_repo + upload_file flow Chapter 5 used, kept deliberately parallel.
#
# Prerequisites (one time):
#   1. A free account:  https://huggingface.co
#   2. A write token:   https://huggingface.co/settings/tokens  (role: "write")
#   3. pip install huggingface_hub
#
# Usage:
#   export HF_TOKEN="hf_..."
#   ./deploy_huggingface.sh <out-dir> <your-username> <space-name>
#
# Example (after: python package_poc.py sample_poc --out ship_out):
#   ./deploy_huggingface.sh ship_out napoleon my-first-poc
#
# When it finishes, your Space builds and goes live at:
#   https://huggingface.co/spaces/<your-username>/<space-name>
set -euo pipefail

OUT_DIR="${1:-}"
USERNAME="${2:-}"
SPACE_NAME="${3:-}"

if [[ -z "$OUT_DIR" || -z "$USERNAME" || -z "$SPACE_NAME" ]]; then
  echo "Usage: ./deploy_huggingface.sh <out-dir> <your-username> <space-name>" >&2
  exit 2
fi

HF_DIR="${OUT_DIR%/}/huggingface"
if [[ ! -d "$HF_DIR" ]]; then
  echo "Not found: ${HF_DIR}" >&2
  echo "Run the packager first, e.g.:  python package_poc.py sample_poc --out ${OUT_DIR}" >&2
  exit 1
fi

if [[ -z "${HF_TOKEN:-}" ]]; then
  echo "Set HF_TOKEN to a write token first: https://huggingface.co/settings/tokens" >&2
  exit 1
fi

REPO_ID="${USERNAME}/${SPACE_NAME}"
echo ">>> Creating (or reusing) Gradio Space: ${REPO_ID}"
python - "$REPO_ID" <<'PY'
import sys, os
from huggingface_hub import create_repo
repo_id = sys.argv[1]
create_repo(repo_id, repo_type="space", space_sdk="gradio",
            token=os.environ["HF_TOKEN"], exist_ok=True)
print(f"    ok: {repo_id}")
PY

echo ">>> Uploading app.py + README.md"
python - "$REPO_ID" "$HF_DIR" <<'PY'
import sys, os
from huggingface_hub import HfApi
repo_id, hf_dir = sys.argv[1], sys.argv[2]
api = HfApi(token=os.environ["HF_TOKEN"])
for fname in ("app.py", "README.md"):
    api.upload_file(path_or_fileobj=os.path.join(hf_dir, fname),
                    path_in_repo=fname, repo_id=repo_id, repo_type="space")
    print(f"    uploaded: {fname}")
PY

echo ""
echo ">>> Done. Your Space is building now — it will be live shortly at:"
echo "    https://huggingface.co/spaces/${REPO_ID}"
