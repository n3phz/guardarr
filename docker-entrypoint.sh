#!/bin/sh
set -eu

PUID="${PUID:-100}"
PGID="${PGID:-101}"

# Reconcile the guardarr group/user with the requested numeric IDs, then drop
# privileges for the application process. The container starts as root so this
# path always runs unless the operator overrides --user explicitly.
if [ "$(id -u)" = "0" ]; then
    cur_gid=$(getent group guardarr | cut -d: -f3 || true)
    if [ "$cur_gid" != "$PGID" ]; then
        groupmod -o -g "$PGID" guardarr
    fi
    cur_uid=$(id -u guardarr)
    if [ "$cur_uid" != "$PUID" ] || [ "$(id -gn guardarr)" != "guardarr" ]; then
        usermod -o -u "$PUID" -g guardarr guardarr
    fi
    # Best-effort: a bind-mounted /config owned by another UID may reject chown;
    # startup must not die there (the remapped user only needs directory perms).
    chown guardarr:guardarr /config 2>/dev/null || true
    exec setpriv --reuid="$PUID" --regid="$PGID" --init-groups env HOME=/config "$@"
fi

# Running under an externally supplied identity (docker run --user): skip the
# remap entirely and hand off to the requested command.
exec env HOME=/config "$@"
