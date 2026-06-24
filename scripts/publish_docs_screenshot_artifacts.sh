#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source_dir="${CONBENCH_DOCS_SCREENSHOT_OUT_DIR:-$root/docs/site/assets/screenshots}"
branch="${CONBENCH_DOCS_SCREENSHOT_BRANCH:-docs-screenshots}"
branch_path="${CONBENCH_DOCS_SCREENSHOT_BRANCH_PATH:-latest}"
remote="${CONBENCH_DOCS_SCREENSHOT_REMOTE:-origin}"

if [ ! -d "$source_dir" ]; then
	echo "missing docs screenshot artifact directory: $source_dir" >&2
	exit 1
fi
if ! compgen -G "$source_dir/dashboard-*.png" >/dev/null; then
	echo "missing docs screenshot PNGs in $source_dir" >&2
	exit 1
fi
if [ ! -f "$source_dir/dashboard-screenshots-evidence.json" ]; then
	echo "missing docs screenshot evidence JSON in $source_dir" >&2
	exit 1
fi

CONBENCH_DOCS_SCREENSHOT_OUT_DIR="$source_dir" bash "$root/scripts/check_docs_screenshots.sh"

tmp="$(mktemp -d "${TMPDIR:-/tmp}/conbench-docs-screenshots-publish.XXXXXX")"
cleanup() {
	rm -rf "$tmp"
}
trap cleanup EXIT

repo="$tmp/repo"
mkdir -p "$repo"
git -C "$repo" init -q
git -C "$repo" checkout --orphan "$branch" >/dev/null 2>&1

remote_url="$(git -C "$root" remote get-url "$remote")"
if [ -n "${GITHUB_TOKEN:-}" ] && [ -n "${GITHUB_REPOSITORY:-}" ]; then
	remote_url="https://x-access-token:${GITHUB_TOKEN}@github.com/${GITHUB_REPOSITORY}.git"
fi
git -C "$repo" remote add origin "$remote_url"

if git -C "$repo" fetch --depth=1 origin "$branch" >/dev/null 2>&1; then
	git -C "$repo" archive --format=tar FETCH_HEAD | tar -x -C "$repo"
fi

mkdir -p "$repo/$branch_path"
rm -f "$repo/$branch_path"/dashboard-*.png
rm -f "$repo/$branch_path"/dashboard-screenshots-evidence.json
cp "$source_dir"/dashboard-*.png "$repo/$branch_path"/
cp "$source_dir"/dashboard-screenshots-evidence.json "$repo/$branch_path"/
if compgen -G "$source_dir/*.png" >/dev/null; then
	find "$source_dir" -maxdepth 1 -type f -name "*.png" ! -name "dashboard-*.png" -exec cp {} "$repo/$branch_path"/ \;
fi

git -C "$repo" add -A
if git -C "$repo" diff --cached --quiet; then
	echo "docs screenshot artifact branch is already up to date"
	exit 0
fi

git -C "$repo" config user.name "${GIT_AUTHOR_NAME:-conbench-docs-bot}"
git -C "$repo" config user.email "${GIT_AUTHOR_EMAIL:-conbench-docs-bot@users.noreply.github.com}"
git -C "$repo" commit -q -m "Update docs screenshot artifacts"
git -C "$repo" push --force origin "HEAD:refs/heads/$branch"
echo "published docs screenshots to orphan branch $branch/$branch_path"
