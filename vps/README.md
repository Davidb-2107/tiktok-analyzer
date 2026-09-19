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

Install the checkout at `/opt/tiktok-analyzer`, create the `tiktok-sync` user,
copy `release-sync.env.example` to `/etc/tiktok-analyzer/release-sync.env`
with mode `0600`, and grant that user write access only to the state, release,
and media roots. Install the two unit files and enable the timer:

```sh
systemctl daemon-reload
systemctl enable --now tiktok-analyzer-release-sync.timer
```

The Hub receives no R2 credentials. A failed sync records machine-readable
state and leaves the active release intact; the optional notification command
is invoked after the second consecutive failure and once on recovery.
