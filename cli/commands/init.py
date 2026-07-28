"""Interactive initializer for handoff."""

from __future__ import annotations

import os
import sys


def _pkg_root() -> str:
    """Absolute path to the cli/ package directory."""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _home_path(*parts: str) -> str:
    return os.path.join(os.path.expanduser("~"), *parts)


def _short(path: str) -> str:
    """Replace the home directory with ~ for display."""
    home = os.path.expanduser("~")
    if path.startswith(home):
        return "~" + path[len(home):]
    return path


def _color(code: str, text: str) -> str:
    if not sys.stdout.isatty() or os.environ.get("NO_COLOR"):
        return text
    return f"\033[{code}m{text}\033[0m"


def _bundled_skill_names(skills_dir: str) -> list[str]:
    """Every bundled Claude Code skill — any subdir holding a SKILL.md.

    Discovered rather than hardcoded so a new backend's skill cannot be
    silently left uninstalled.
    """
    return sorted(
        name for name in os.listdir(skills_dir)
        if os.path.isfile(os.path.join(skills_dir, name, "SKILL.md"))
    )


# Where each host looks for skills.
_HOST_SKILL_DIRS = {
    "claude": (".claude", "skills"),
    "codex": (".codex", "skills"),
}

# Codex skills must be regular-file hard links. Claude Code keeps symlinks so
# the editable source relationship remains visible there.
_HOST_LINK_KINDS = {
    "claude": "soft link",
    "codex": "hard link",
}

# A host must not see the skill that dispatches to its own model: the names
# collide and the model reads "ask Opus" as "dispatch a background handoff run".
_HOST_EXCLUDED_SKILLS = {
    "claude": {"handoff-opus"},
    "codex": set(),
}


def _planned_links():
    """Return (kind, src, dest) tuples for link files only (no config)."""
    skills_dir = os.path.join(_pkg_root(), "skills")
    links = []
    for host in sorted(_HOST_SKILL_DIRS):
        for skill_name in _bundled_skill_names(skills_dir):
            if skill_name in _HOST_EXCLUDED_SKILLS[host]:
                continue
            links.append((
                _HOST_LINK_KINDS[host],
                os.path.join(skills_dir, skill_name, "SKILL.md"),
                _home_path(*_HOST_SKILL_DIRS[host], skill_name, "SKILL.md"),
            ))

            # Codex may invoke handoff-codex only when the user explicitly
            # mentions $handoff-codex. This metadata is intentionally not
            # installed for any other handoff skill or host.
            if host == "codex" and skill_name == "handoff-codex":
                metadata_parts = ("agents", "openai.yaml")
                links.append((
                    "hard link",
                    os.path.join(skills_dir, skill_name, *metadata_parts),
                    _home_path(
                        *_HOST_SKILL_DIRS[host], skill_name, *metadata_parts
                    ),
                ))
    return links


def _excluded_skill_links():
    """Previously-installed links for skills a host must no longer see.

    Only links to our bundled SKILL.md files are reported — a real file the
    user put there is left alone. Both symlinks and hard links are recognized.
    """
    skills_dir = os.path.join(_pkg_root(), "skills")
    stale = []
    for host, excluded in sorted(_HOST_EXCLUDED_SKILLS.items()):
        for skill_name in sorted(excluded):
            src = os.path.join(skills_dir, skill_name, "SKILL.md")
            dest = _home_path(*_HOST_SKILL_DIRS[host], skill_name, "SKILL.md")
            is_our_symlink = (
                os.path.islink(dest)
                and os.path.realpath(dest).startswith(skills_dir + os.sep)
            )
            is_our_hardlink = (
                not os.path.islink(dest)
                and os.path.isfile(dest)
                and os.path.samefile(src, dest)
            )
            if is_our_symlink or is_our_hardlink:
                stale.append(dest)
    return stale


def _legacy_agent_files():
    """Codex `.toml` subagents installed before the skills migration."""
    agents_dir = _home_path(".codex", "agents")
    if not os.path.isdir(agents_dir):
        return []
    return [
        os.path.join(agents_dir, name)
        for name in sorted(os.listdir(agents_dir))
        if name.startswith("handoff-") and name.endswith(".toml")
    ]


def _legacy_agent_backup_path(path: str) -> str:
    """Choose a backup name without overwriting an earlier migration."""
    base = f"{path}.removed.bak"
    candidate = base
    suffix = 1
    while os.path.lexists(candidate):
        candidate = f"{base}.{suffix}"
        suffix += 1
    return candidate


def _print_plan():
    from ..config import user_config_path

    print(_color("1", "handoff initialization"))
    print("")

    links = _planned_links()
    print("The following will be created/updated:")
    for kind, src, dest in links:
        print(f"  {kind}: {_short(dest)} -> {_short(src)}")

    stale_links = _excluded_skill_links()
    if stale_links:
        print("\nThe following superseded links will be removed:")
        for path in stale_links:
            print(f"  remove: {_short(path)}")

    legacy_agents = _legacy_agent_files()
    if legacy_agents:
        print("\nThe following legacy Codex agents will be backed up:")
        for path in legacy_agents:
            backup = _legacy_agent_backup_path(path)
            print(f"  move: {_short(path)} -> {_short(backup)}")

    config_path = user_config_path()
    if os.path.isfile(config_path):
        print(f"\nConfig {_short(config_path)} already exists — will not be overwritten.")
    else:
        print(f"\nConfig {_short(config_path)} will be written.")

    print("")


def _confirm() -> bool:
    _print_plan()
    try:
        answer = input("Type Y to continue, anything else to exit: ").strip()
    except EOFError:
        answer = ""
    return answer.lower() == "y"


def _create_links():
    """Install every planned skill link and migrate superseded integrations.

    Consumes `_planned_links()` directly so what `handoff init` previews is
    exactly what it writes.
    """
    links = _planned_links()
    link_functions = {
        "hard link": os.link,
        "soft link": os.symlink,
    }
    for kind, src, dest in links:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        if os.path.lexists(dest):
            os.remove(dest)
        link_functions[kind](src, dest)

    removed = 0
    for stale in _excluded_skill_links():
        os.remove(stale)
        removed += 1
        # Drop the skill's directory too, once its SKILL.md is gone.
        parent = os.path.dirname(stale)
        if os.path.basename(stale) == "SKILL.md" and not os.listdir(parent):
            os.rmdir(parent)

    moved_agents = []
    for legacy in _legacy_agent_files():
        backup = _legacy_agent_backup_path(legacy)
        os.rename(legacy, backup)
        moved_agents.append((legacy, backup))

    print(f"✓ Created {len(links)} skill links")
    if removed:
        print(f"✓ Removed {removed} superseded links")
    if moved_agents:
        print(
            _color(
                "1;33",
                "WARNING: Legacy Codex agent files were disabled and backed up:",
            ),
            file=sys.stderr,
        )
        for legacy, backup in moved_agents:
            print(
                f"  {_short(legacy)} -> {_short(backup)}",
                file=sys.stderr,
            )


def run_init(assume_yes: bool = False):
    if not assume_yes and not _confirm():
        print("handoff: initialization cancelled")
        sys.exit(1)

    print("")
    from ..config import user_config_path, write_default_user_config

    wrote_config = write_default_user_config()
    if wrote_config:
        print(f"✓ Wrote {_short(user_config_path())}")
    else:
        print(f"  Config {_short(user_config_path())} already exists (skipped)")

    _create_links()

    readme_url = "https://github.com/dazuiba/handoff#configuration"

    print("")
    print("Next:")
    print(f"  1. Edit {_short(user_config_path())} and replace"
          f" ${{DEEPSEEK_API_KEY}} with your API key.")
    print(f"  2. For help, see {readme_url}")


def cmd_init(args):
    if args and args[0] in ("-h", "--help"):
        print("usage: handoff init [-y|--yes]")
        return
    assume_yes = False
    for arg in args:
        if arg in ("-y", "--yes"):
            assume_yes = True
        else:
            print(f"handoff: init: unexpected argument '{arg}'", file=sys.stderr)
            sys.exit(2)
    run_init(assume_yes=assume_yes)
