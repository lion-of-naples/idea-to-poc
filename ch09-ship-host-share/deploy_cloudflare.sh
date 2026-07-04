#!/usr/bin/env bash
# deploy_cloudflare.sh — publish the generated Cloudflare Pages artifacts.
#
# The Chapter 9 packager writes a Cloudflare artifact set into:
#     <out>/cloudflare/wrangler.toml
#     <out>/cloudflare/public/index.html
#
# This script deploys that static site to Cloudflare Pages with wrangler.
#
# Prerequisites (one time):
#   1. A free Cloudflare account:  https://dash.cloudflare.com/sign-up
#   2. Node + wrangler:            npm install -g wrangler
#   3. Log in once:                wrangler login
#
# Usage:
#   ./deploy_cloudflare.sh <out-dir> <project-name>
#
# Example (after: python package_poc.py sample_poc --out ship_out):
#   ./deploy_cloudflare.sh ship_out my-first-poc
#
# When it finishes, wrangler prints the live *.pages.dev URL.
set -euo pipefail

OUT_DIR="${1:-}"
PROJECT="${2:-}"

if [[ -z "$OUT_DIR" || -z "$PROJECT" ]]; then
  echo "Usage: ./deploy_cloudflare.sh <out-dir> <project-name>" >&2
  exit 2
fi

PUBLIC_DIR="${OUT_DIR%/}/cloudflare/public"
if [[ ! -d "$PUBLIC_DIR" ]]; then
  echo "Not found: ${PUBLIC_DIR}" >&2
  echo "Run the packager first, e.g.:  python package_poc.py sample_poc --out ${OUT_DIR}" >&2
  exit 1
fi

if ! command -v wrangler >/dev/null 2>&1; then
  echo "wrangler not found. Install it:  npm install -g wrangler" >&2
  exit 1
fi

echo ">>> Deploying ${PUBLIC_DIR} to Cloudflare Pages project '${PROJECT}'"
wrangler pages deploy "$PUBLIC_DIR" --project-name "$PROJECT"

echo ""
echo ">>> Done. wrangler printed your live *.pages.dev URL above."
