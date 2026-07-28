import os

from cli.commands import init


def _dests(tmp_home):
    """Planned link destinations, home-relative."""
    return {
        os.path.relpath(dest, str(tmp_home))
        for _kind, _src, dest in init._planned_links()
    }


def _links_by_dest(tmp_home):
    """Planned links keyed by home-relative destination."""
    return {
        os.path.relpath(dest, str(tmp_home)): (kind, src, dest)
        for kind, src, dest in init._planned_links()
    }


def test_claude_excludes_opus_but_codex_installs_explicit_only_codex_skill(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("HOME", str(tmp_path))
    dests = _dests(tmp_path)

    assert ".claude/skills/handoff-opus/SKILL.md" not in dests
    assert ".codex/skills/handoff-codex/SKILL.md" in dests
    assert ".codex/skills/handoff-codex/agents/openai.yaml" in dests
    assert ".codex/skills/handoff-opus/SKILL.md" in dests
    assert ".claude/skills/handoff-codex/SKILL.md" in dests


def test_neutral_skills_install_on_both_hosts(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    dests = _dests(tmp_path)

    for skill in ("handoff-ds", "handoff-gemini"):
        assert f".claude/skills/{skill}/SKILL.md" in dests
        assert f".codex/skills/{skill}/SKILL.md" in dests


def test_codex_uses_hard_links_and_claude_uses_soft_links(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    links = _links_by_dest(tmp_path)

    assert links[".codex/skills/handoff-opus/SKILL.md"][0] == "hard link"
    assert links[".codex/skills/handoff-codex/SKILL.md"][0] == "hard link"
    assert (
        links[".codex/skills/handoff-codex/agents/openai.yaml"][0]
        == "hard link"
    )
    assert links[".claude/skills/handoff-codex/SKILL.md"][0] == "soft link"


def test_create_links_uses_each_hosts_planned_link_type(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    init._create_links()

    for relative_dest, (kind, src, dest) in _links_by_dest(tmp_path).items():
        if relative_dest.startswith(".codex/"):
            assert kind == "hard link"
            assert not os.path.islink(dest)
            assert os.path.samefile(src, dest)
        else:
            assert kind == "soft link"
            assert os.path.islink(dest)
            assert os.path.realpath(dest) == os.path.realpath(src)


def test_every_bundled_skill_reaches_at_least_one_host(monkeypatch, tmp_path):
    """Guards the bug where the install list was hardcoded and silently
    dropped a bundled skill."""
    monkeypatch.setenv("HOME", str(tmp_path))
    dests = _dests(tmp_path)

    skills_dir = os.path.join(init._pkg_root(), "skills")
    for skill in init._bundled_skill_names(skills_dir):
        assert any(f"/{skill}/SKILL.md" in d for d in dests), f"{skill} installed nowhere"


def test_no_toml_agents_are_installed(monkeypatch, tmp_path):
    """Codex `.toml` subagents are superseded by skills."""
    monkeypatch.setenv("HOME", str(tmp_path))
    assert not [d for d in _dests(tmp_path) if d.endswith(".toml")]


def test_legacy_toml_agents_are_backed_up_with_warning(
    monkeypatch, tmp_path, capsys
):
    monkeypatch.setenv("HOME", str(tmp_path))
    legacy = tmp_path / ".codex" / "agents" / "handoff-ds.toml"
    legacy.parent.mkdir(parents=True)
    legacy.write_text("user data", encoding="utf-8")

    init._create_links()

    backup = legacy.with_name("handoff-ds.toml.removed.bak")
    assert not legacy.exists()
    assert backup.read_text(encoding="utf-8") == "user data"
    captured = capsys.readouterr()
    assert "WARNING: Legacy Codex agent files were disabled and backed up" in captured.err
    assert "handoff-ds.toml.removed.bak" in captured.err


def test_legacy_agent_backup_does_not_overwrite_existing_backup(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("HOME", str(tmp_path))
    agents = tmp_path / ".codex" / "agents"
    agents.mkdir(parents=True)
    legacy = agents / "handoff-ds.toml"
    existing_backup = agents / "handoff-ds.toml.removed.bak"
    legacy.write_text("legacy", encoding="utf-8")
    existing_backup.write_text("previous backup", encoding="utf-8")

    init._create_links()

    assert existing_backup.read_text(encoding="utf-8") == "previous backup"
    assert (agents / "handoff-ds.toml.removed.bak.1").read_text(
        encoding="utf-8"
    ) == "legacy"


def test_excluded_link_cleanup_ignores_user_owned_files(monkeypatch, tmp_path):
    """A real file the user placed at an excluded path is not ours to delete."""
    monkeypatch.setenv("HOME", str(tmp_path))
    user_skill = tmp_path / ".claude" / "skills" / "handoff-opus" / "SKILL.md"
    user_skill.parent.mkdir(parents=True)
    user_skill.write_text("my own skill", encoding="utf-8")

    assert init._excluded_skill_links() == []


def test_excluded_link_cleanup_targets_our_symlink(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    src = os.path.join(init._pkg_root(), "skills", "handoff-opus", "SKILL.md")
    dest = tmp_path / ".claude" / "skills" / "handoff-opus" / "SKILL.md"
    dest.parent.mkdir(parents=True)
    os.symlink(src, dest)

    assert init._excluded_skill_links() == [str(dest)]


def test_excluded_link_cleanup_targets_our_hardlink(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    src = os.path.join(init._pkg_root(), "skills", "handoff-opus", "SKILL.md")
    dest = tmp_path / ".claude" / "skills" / "handoff-opus" / "SKILL.md"
    dest.parent.mkdir(parents=True)
    os.link(src, dest)

    assert init._excluded_skill_links() == [str(dest)]
