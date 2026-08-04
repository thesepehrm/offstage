from pathlib import Path

from offstage.cli import main

SKILL = Path(__file__).resolve().parents[1] / "src/offstage/skill/offstage-qa/SKILL.md"


def test_skill_frontmatter():
    text = SKILL.read_text()
    assert text.startswith("---\n")
    head = text.split("---")[1]
    assert "name: offstage-qa" in head
    assert "description:" in head


def test_skill_install(tmp_path, capsys):
    assert main(["skill", "install", "--target", str(tmp_path)]) == 0
    installed = tmp_path / "offstage-qa" / "SKILL.md"
    assert installed.exists()
    assert installed.read_text() == SKILL.read_text()
    assert "installed skill" in capsys.readouterr().out


def test_plugin_skill_symlink_resolves():
    # The repo-root skills/ dir (Claude Code plugin layout) must point at the
    # same files the pip package installs from.
    link = Path(__file__).resolve().parents[1] / "skills/offstage-qa/SKILL.md"
    assert link.read_text() == SKILL.read_text()
