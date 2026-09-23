"""Static contract tests for the Saltbox-compatible container entrypoint.

These guard the UID/GID drop-privileges mechanism without requiring a Docker
daemon: docker-entrypoint.sh is parsed as text and asserted against the
invariants the Saltbox integration depends on.
"""

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = REPO_ROOT / "docker-entrypoint.sh"
DOCKERFILE = REPO_ROOT / "Dockerfile"


@pytest.fixture(scope="module")
def entrypoint_text() -> str:
    return ENTRYPOINT.read_text()


@pytest.fixture(scope="module")
def dockerfile_text() -> str:
    return DOCKERFILE.read_text()


class TestEntrypointExists:
    def test_entrypoint_file_exists(self):
        assert ENTRYPOINT.is_file(), "docker-entrypoint.sh must exist at repo root"

    def test_dockerfile_references_entrypoint(self, dockerfile_text):
        assert "docker-entrypoint.sh" in dockerfile_text


class TestEntrypointContract:
    def test_uses_posix_sh_and_strict_mode(self, entrypoint_text):
        assert entrypoint_text.startswith("#!/bin/sh")
        assert "set -eu" in entrypoint_text

    def test_default_ids_match_image_build_identity(self, entrypoint_text):
        # Defaults preserve the original image behavior (system user 100/101).
        assert 'PUID="${PUID:-100}"' in entrypoint_text
        assert 'PGID="${PGID:-101}"' in entrypoint_text

    def test_root_only_remap_guard(self, entrypoint_text):
        # Remap logic must only run when invoked as root.
        assert 'if [ "$(id -u)" = "0" ]; then' in entrypoint_text

    def test_reconciles_group_then_user(self, entrypoint_text):
        assert "groupmod -o -g \"$PGID\" guardarr" in entrypoint_text
        assert "usermod -o -u \"$PUID\" -g guardarr guardarr" in entrypoint_text

    def test_drops_privileges_via_setpriv(self, entrypoint_text):
        assert "exec setpriv --reuid=\"$PUID\" --regid=\"$PGID\" --init-groups" in entrypoint_text

    def test_config_chown_is_tolerant(self, entrypoint_text):
        # A pre-existing bind mount may reject chown; startup must not die there.
        assert "chown guardarr:guardarr /config 2>/dev/null || true" in entrypoint_text

    def test_data_never_chowned(self, entrypoint_text):
        # /data may be mounted read-only; ownership must never be touched.
        chown_lines = [l for l in entrypoint_text.splitlines() if "chown" in l]
        assert chown_lines, "expected at least one chown line"
        for line in chown_lines:
            assert "/data" not in line, f"entrypoint must not chown /data: {line}"

    def test_nonroot_passthrough_execs_cmd(self, entrypoint_text):
        assert 'exec env HOME=/config "$@"' in entrypoint_text

    def test_entrypoint_always_drops_to_target_ids(self, entrypoint_text):
        # The setpriv exec must be the last command of the root branch (the
        # outer `if root` block ends right after it), so nothing else runs as
        # root once the drop is reached.
        lines = [l.strip() for l in entrypoint_text.splitlines() if l.strip() and not l.strip().startswith("#")]
        setpriv_idx = next(i for i, l in enumerate(lines) if l.startswith("exec setpriv"))
        assert lines[setpriv_idx + 1] == "fi"
        # Only the non-root passthrough exec follows the root branch.
        assert lines[setpriv_idx + 2].startswith("exec ")

    def test_no_world_writable_permissions(self, entrypoint_text):
        assert "777" not in entrypoint_text


class TestDockerfileContract:
    def test_build_time_identity_defaults(self, dockerfile_text):
        assert 'ENV PUID=100' in dockerfile_text
        assert 'PGID=101' in dockerfile_text

    def test_creates_guardarr_user_with_numeric_ids(self, dockerfile_text):
        assert 'groupadd -r guardarr -g "${PGID}"' in dockerfile_text
        assert 'useradd -r -g guardarr -u "${PUID}" guardarr' in dockerfile_text

    def test_no_baked_user_directive(self, dockerfile_text):
        # The entrypoint must start as root so it can remap PUID/PGID and then
        # drop privileges via setpriv. A baked-in USER directive would skip the
        # remap path entirely (verified: PID 1 stayed 100:101 with USER set).
        user_lines = [l for l in dockerfile_text.splitlines() if l.strip().startswith("USER ")]
        assert not user_lines, f"Dockerfile must not bake a USER directive: {user_lines}"

    def test_app_files_owned_by_guardarr_at_build(self, dockerfile_text):
        # Even though the container starts as root, the application tree is
        # chowned to guardarr so the dropped-privilege process owns its files.
        assert "chown -R guardarr:guardarr /app /config /data" in dockerfile_text

    def test_healthcheck_targets_api_health(self, dockerfile_text):
        assert "http://localhost:8000/api/health" in dockerfile_text

    def test_exposes_port_8000(self, dockerfile_text):
        assert "EXPOSE 8000" in dockerfile_text
