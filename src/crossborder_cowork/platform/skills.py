from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    path: Path

    def load(self) -> str:
        return self.path.read_text(encoding="utf-8")


class SkillRegistry:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def discover(self) -> list[Skill]:
        skills: list[Skill] = []
        if not self.root.exists():
            return skills
        for path in sorted(self.root.glob("*/SKILL.md")):
            raw = path.read_text(encoding="utf-8")
            frontmatter = raw.split("---", 2)[1] if raw.startswith("---") and raw.count("---") >= 2 else ""
            name_match = re.search(r"^name:\s*(.+)$", frontmatter, re.MULTILINE)
            desc_match = re.search(r"^description:\s*(.+)$", frontmatter, re.MULTILINE)
            skills.append(Skill(
                name=(name_match.group(1).strip() if name_match else path.parent.name),
                description=(desc_match.group(1).strip() if desc_match else ""),
                path=path,
            ))
        return skills

    def get(self, name: str) -> Skill:
        for skill in self.discover():
            if skill.name == name or skill.path.parent.name == name:
                return skill
        raise KeyError(name)

