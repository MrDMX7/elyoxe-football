#!/usr/bin/env bash
# snapshot_push.sh: pack the data a build needs and push it to the branch `data-snapshot`, so a cloud
# session that cannot reach AWS or the CloudFront hosts can still build and test the site.
#   run it where AWS works (the Fold chroot), from any clone of this repo:  bash tools/snapshot_push.sh
#   packs: s3://<data bucket>/v1 (what the build fetches as TIFO_DATA), site/cache, and the research dir
#   the branch holds one commit and is force-pushed each time; main and the work branches are not touched
#   SNAP_NO_S3=1 skips the bucket; SNAP_PART=49m sets the part size (GitHub rejects files over 100 MB)
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REGION="${FOOTBALL_REGION:-ap-south-1}" STACK="${FOOTBALL_STACK:-elyoxe-football}"
RSD="$HOME/workspace/research/tifo-2026-09-27" PART="${SNAP_PART:-49m}"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/snap"

if [ -z "${SNAP_NO_S3:-}" ]; then
  B=$(aws cloudformation describe-stacks --region "$REGION" --stack-name "$STACK" \
    --query "Stacks[0].Outputs[?OutputKey=='Bucket'].OutputValue" --output text)
  echo "data: s3://$B/v1"
  # objects stay as stored (JSON is gzip bytes); snapshot_pull.sh serves them with Content-Encoding: gzip
  aws s3 sync "s3://$B/v1" "$TMP/snap/v1" --region "$REGION" --only-show-errors
fi
[ -d "$REPO/site/cache" ] && { echo "site/cache"; cp -a "$REPO/site/cache" "$TMP/snap/site-cache"; rm -f "$TMP/snap/site-cache/deploy.lock"; }
[ -d "$RSD" ] && { echo "research: $RSD"; cp -a "$RSD" "$TMP/snap/research"; }

{ echo "made: $(date -u +%FT%TZ)"; echo "host: $(hostname)"; echo "repo head: $(git -C "$REPO" rev-parse --short HEAD) ($(git -C "$REPO" rev-parse --abbrev-ref HEAD))"
  du -sh "$TMP/snap"/* 2>/dev/null; } > "$TMP/MANIFEST.txt"
cat "$TMP/MANIFEST.txt"

mkdir -p "$TMP/parts"
tar -C "$TMP/snap" -czf - . | split -b "$PART" -d -a 3 - "$TMP/parts/snap.tgz."
cp "$TMP/MANIFEST.txt" "$TMP/parts/"
( cd "$TMP/parts" && sha256sum snap.tgz.* > SHA256SUMS )
echo "parts: $(ls "$TMP/parts" | grep -c '^snap.tgz') ($(du -sh "$TMP/parts" | cut -f1))"

# a one-commit tree built with plumbing: no checkout, the current worktree stays as it is
TREE=$(for f in "$TMP/parts"/*; do printf '100644 blob %s\t%s\n' "$(git -C "$REPO" hash-object -w "$f")" "${f##*/}"; done | git -C "$REPO" mktree)
[ -n "$TREE" ] || { echo "could not build the snapshot tree" >&2; exit 1; }
C=$(git -C "$REPO" commit-tree "$TREE" -m "data snapshot $(date -u +%FT%TZ)")
for i in 0 2 4 8 16; do
  [ "$i" -gt 0 ] && { echo "push failed, retry in ${i}s"; sleep "$i"; }
  git -C "$REPO" push -f origin "$C:refs/heads/data-snapshot" && { echo "pushed $C to data-snapshot"; exit 0; }
done
exit 1
