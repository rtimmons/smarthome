# Incomplete-download maintenance

The cloud cart-import role installs and enables
`usenet-incomplete-maintenance.timer`, which runs daily at approximately
04:30 with a randomized delay of up to 30 minutes. The timer is intentionally
non-persistent, so a missed run does not start unexpectedly during deployment.

The job may remove only immediate child directories of the mounted
`downloads/incomplete` filesystem when all of these conditions hold:

- the directory is at least seven days old;
- SAB has no post-processing work and every queue item is individually paused;
- no SAB queue/history path or cart-import journal references the directory;
- the directory contains only regular, singly-linked files; and
- the mount and shared cache lock are available.

Anything ambiguous is retained for the next run. Each successful run writes a
0600 JSON receipt under `state/catalog/maintenance/incomplete-cleanup/` with
counts and reclaimed bytes, but never stores media names, URLs, or queue IDs.
The receipt directory and timer are managed by the existing
`just usenet-configure-cart-import` deployment workflow.
