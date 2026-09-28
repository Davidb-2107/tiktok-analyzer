# VPS release sync

The timer prepares the operator-pinned release from private R2. It performs
exact-key `GET` requests for `manifest.json`, `payload.json`, and the media
objects named by `media_digests`. It never lists, writes, deletes, or activates
an R2 object, and it never changes the Hub's active release.

The pin is a single `sha256:<64 lowercase hex>` line. Only the operator command
writes it; every change is appended to `<pin>.journal` with actor, old digest,
new digest, reason, and timestamp:

```sh
python -m vps.release_sync pin \
  --digest sha256:<digest> \
  --actor operator@example.com \
  --reason "promote validated transition release"
```

Install the checkout at `/home/projects/tiktok-analyzer` (the same checkout
builds the Hub image and runs activation), create the `tiktok-sync` user,
copy `release-sync.env.example` to `/etc/tiktok-analyzer/release-sync.env`
with mode `0600`, and grant that user write access only to the state, release,
and media roots. The state directory is a shared group boundary: make it
`tiktok-sync:tiktok-sync` with mode `2770`, and state files are `0640` so the
Hub can read them without receiving R2 credentials. Install the two unit files
and enable the timer:

```sh
systemctl daemon-reload
systemctl enable --now tiktok-analyzer-release-sync.timer
```

The Hub receives no R2 credentials. A failed sync records machine-readable
state and leaves the active release intact; the optional notification command
is invoked after the second consecutive failure and once on recovery.

Activation is operator-only and takes its target digest explicitly. It refuses
anything that is not the current pin, is not completely materialized, is
legacy, or fails revalidation. The Hub reads the canonical one-line
`active-release` state from the read-only state-directory mount; activation is
its only writer. The external `/hub` check must return the same `release_id`.
Run activation from a shell that can reach `RELEASE_ACTIVATE_EXTERNAL_URL`
(the VPS host, not the ttyd container): it refuses with `HubUnreachable`
before touching state or reloading the Hub when that URL gives no HTTP answer.
A forward activation also requires the private gate attestation
`<RELEASE_R2_PREFIX>gates/sha256/<digest>.json`, which the Vault
`published-snapshot-gate.yml` writes only when every gate check passes. It is
read with the same read-only R2 credentials as the sync; a missing, malformed
or non-pass attestation raises `GateNotPassed` before any change, and the
journal records the gate run URL. The running Hub container must also be
aligned with the gate: its `org.opencontainers.image.revision` label must name
a commit whose image inputs (`Dockerfile.prod .dockerignore .gitattributes
backend publication frontend`) are identical, in this checkout, to the
attestation's `analyzer_ref`. A missing label or a mismatch raises
`ImageNotAligned` before any change. The check runs again after the reload; a
mismatch there restores the release pointers and raises `ImageChanged`, but
does not restore the previous image. The journal records `image_revision`.
Rollback to the previous release is exempt from both the gate and the image
check.
If the state is absent, malformed, unreadable, or a symlink, the Hub fails
closed rather than falling back to a stale environment value:

```sh
python -m vps.activation activate \
  --digest sha256:<digest> \
  --actor operator@example.com \
  --reason "promote gated release"
```

`active-release` is critical Hub state. If it is absent or invalid, do not
edit it by hand: stop the timer, inspect the pin and activation journal, sync
the pinned digest, then run the explicit activation command above. The Hub
must remain fail-closed until that state is restored and externally verified.

Rollback writes the previous active digest to the pin first, synchronizes it if
needed, then calls the same activation primitive. Local GC protects active,
previous, pinned, and every media file referenced by those releases; it never
calls R2 and deletes nothing when active or pin state is indeterminate:

```sh
python -m vps.activation rollback --actor operator@example.com --reason "restore previous release"
python -m vps.activation gc
```

## Rebuilding the Hub image

Compose never builds the production image (`pull_policy: never`, no `build:`).
Suspend activations, then build from the tracked tree so untracked or ignored
files cannot enter the build context.

Run every command on the VPS host (not the ttyd container), from the checkout
that builds the image and runs activation, `/home/projects/tiktok-analyzer`,
in a shell that has loaded the activation environment. `check` needs the same
variables as `activate`: the R2 read keys and prefix to read the gate
attestation, the state root to read `active-release`, and
`RELEASE_ACTIVATE_RELOAD_COMMAND` and `RELEASE_ACTIVATE_EXTERNAL_URL`.

```sh
cd /home/projects/tiktok-analyzer
set -a; . /etc/tiktok-analyzer/release-sync.env; set +a
docker tag "$(docker inspect --type container tiktok-analyzer --format '{{.Image}}')" tiktok-analyzer-hub:previous
rev="$(git rev-parse HEAD)"
git archive "$rev" | docker build -f Dockerfile.prod --label org.opencontainers.image.revision="$rev" -t tiktok-analyzer-hub -
python -m vps.activation check --image tiktok-analyzer-hub
$RELEASE_ACTIVATE_RELOAD_COMMAND
python -m vps.activation check
```

`check` is read-only: it requires the active release's gate attestation, checks
the image alignment and, without `--image`, verifies `/hub`. It detects an
incompatible image; it does not prevent one that was deployed without it.

### Falling back to the previous image

The previous image may predate the active release. For a labelled previous
image, check it against the active release before retagging, then check the
running container and `/hub` after the reload (same directory and environment
as above):

```sh
python -m vps.activation check --image tiktok-analyzer-hub:previous
docker tag tiktok-analyzer-hub:previous tiktok-analyzer-hub
$RELEASE_ACTIVATE_RELOAD_COMMAND
python -m vps.activation check
```

An image without a revision label, such as the pre-ADR-0007 image `7019d419`,
cannot pass `check`. Fall back to it only while the active release is the one
that image already served, then confirm by hand that `/hub` returns the
`release_id` in `active-release`. Forward activations stay refused until an
aligned, labelled image is deployed again:

```sh
docker tag tiktok-analyzer-hub:previous tiktok-analyzer-hub
$RELEASE_ACTIVATE_RELOAD_COMMAND
curl -fsS "$RELEASE_ACTIVATE_EXTERNAL_URL"
cat "$RELEASE_SYNC_STATE_ROOT/active-release"
```
