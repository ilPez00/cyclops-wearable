"""Skills loader — reuses SKILL.md files from disk (same shape as ~/.hermes/skills).

A skill is a markdown file with YAML frontmatter (name, description) and a body.
The agent can surface skill instructions to the model as extra system context,
and skills can register tools. This mirrors how Hermes loads skills on disk.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Skill:
    name: str
    description: str
    body: str
    path: str

    def system_block(self) -> str:
        return f"## Skill: {self.name}\n{self.description}\n\n{self.body}"


_FRONT = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


class Skills:
    def __init__(self, dirs: list[str]):
        self.dirs = [Path(d).expanduser() for d in dirs]
        self._cache: dict[str, Skill] = {}

    def load(self, name: str) -> Optional[Skill]:
        if name in self._cache:
            return self._cache[name]
        for d in self.dirs:
            p = d / name / "SKILL.md"
            if p.exists():
                s = self._parse(p)
                self._cache[name] = s
                return s
            # flat layout: skills/<name>.md
            p2 = d / f"{name}.md"
            if p2.exists():
                s = self._parse(p2)
                self._cache[name] = s
                return s
        return None

    def load_all(self) -> list[Skill]:
        out = []
        for d in self.dirs:
            if not d.exists():
                continue
            for sk in d.iterdir():
                if sk.is_dir() and (sk / "SKILL.md").exists():
                    out.append(self._parse(sk / "SKILL.md"))
                elif sk.is_file() and sk.suffix == ".md":
                    out.append(self._parse(sk))
        return out

    def system_block(self, names: list[str] | None = None) -> str:
        skills = [self.load(n) for n in (names or [])] if names else self.load_all()
        skills = [s for s in skills if s]
        return "\n\n".join(s.system_block() for s in skills)

    @staticmethod
    def _parse(p: Path) -> Skill:
        text = p.read_text(encoding="utf-8", errors="ignore")
        m = _FRONT.match(text)
        name = p.parent.name if p.name == "SKILL.md" else p.stem
        desc = ""
        body = text
        if m:
            fm = m.group(1)
            body = text[m.end():]
            for line in fm.splitlines():
                if line.lower().startswith("name:"):
                    name = line.split(":", 1)[1].strip()
                elif line.lower().startswith("description:"):
                    desc = line.split(":", 1)[1].strip()
        return Skill(name=name, description=desc, body=body, path=str(p))
