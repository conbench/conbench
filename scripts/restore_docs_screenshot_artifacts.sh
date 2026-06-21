#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
branch="${CONBENCH_DOCS_SCREENSHOT_BRANCH:-docs-screenshots}"
branch_path="${CONBENCH_DOCS_SCREENSHOT_BRANCH_PATH:-latest}"
remote="${CONBENCH_DOCS_SCREENSHOT_REMOTE:-origin}"
asset_dir="${CONBENCH_DOCS_SCREENSHOT_ASSET_DIR:-$root/docs/site/assets/screenshots}"
required="${CONBENCH_DOCS_SCREENSHOT_RESTORE_REQUIRED:-1}"

tmp="$(mktemp -d "${TMPDIR:-/tmp}/conbench-docs-screenshots-restore.XXXXXX")"
cleanup() {
	rm -rf "$tmp"
}
trap cleanup EXIT

repo="$tmp/repo"
mkdir -p "$repo"
git -C "$repo" init -q

remote_url="$(git -C "$root" remote get-url "$remote")"
if [ -n "${GITHUB_TOKEN:-}" ] && [ -n "${GITHUB_REPOSITORY:-}" ]; then
	remote_url="https://x-access-token:${GITHUB_TOKEN}@github.com/${GITHUB_REPOSITORY}.git"
fi
git -C "$repo" remote add origin "$remote_url"

if ! git -C "$repo" fetch --depth=1 origin "$branch" >/dev/null 2>&1; then
	if [ "$required" = "0" ]; then
		echo "docs screenshot artifact branch $branch not found; restore skipped"
		exit 0
	fi
	echo "docs screenshot artifact branch $branch not found" >&2
	exit 1
fi

mkdir -p "$tmp/extract"
if ! git -C "$repo" archive --format=tar FETCH_HEAD "$branch_path" | tar -x -C "$tmp/extract"; then
	echo "docs screenshot artifact path $branch_path not found on $branch" >&2
	exit 1
fi

rm -rf "$asset_dir"
mkdir -p "$asset_dir"
cp -R "$tmp/extract/$branch_path"/. "$asset_dir"/

CONBENCH_DOCS_SCREENSHOT_OUT_DIR="$asset_dir" bash "$root/scripts/check_docs_screenshots.sh"
python3 -B "$root/scripts/docs_links.py" --verify-generated-screenshots "$asset_dir"
echo "restored docs screenshot artifacts from $branch/$branch_path"
