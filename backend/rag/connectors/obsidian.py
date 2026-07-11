import re
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

import frontmatter

from .base import SourceConnector, SourceDocument

# Directories never scanned, on top of any directory starting with a dot.
IGNORED_DIRS = {".obsidian", ".trash"}

# Metadata keys owned by the connector/pipeline; frontmatter cannot override them.
RESERVED_METADATA_KEYS = {
    "user_id",
    "source",
    "note_path",
    "note_title",
    "folder",
    "modified_at",
    "heading_path",
    "outlinks",
}

IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "svg", "webp", "bmp"}

# ![[file]] embeds; wikilinks as [[target(#heading)(|alias)]]; inline #tags.
_EMBED_RE = re.compile(r"!\[\[([^\]]+?)\]\]")
_WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#([^\]|]*))?(?:\|([^\]]+))?\]\]")
_INLINE_TAG_RE = re.compile(r"(?<![\w#])#([A-Za-z][\w/-]*)")


def _normalize_tags(value) -> list[str]:
    """Frontmatter tags can be a list, a comma-separated string, or None."""
    if value is None:
        return []
    if isinstance(value, str):
        items = value.split(",")
    elif isinstance(value, list):
        items = value
    else:
        items = [value]
    return [str(item).strip().lstrip("#") for item in items if str(item).strip()]


def _strip_image_embeds(content: str) -> str:
    def replace(match: re.Match) -> str:
        target = match.group(1).split("|")[0].strip()
        extension = target.rsplit(".", 1)[-1].lower() if "." in target else ""
        if extension in IMAGE_EXTENSIONS:
            return ""
        # Non-image embeds ([[!Note]]) behave like regular wikilinks.
        return f"[[{match.group(1)}]]"

    return _EMBED_RE.sub(replace, content)


def _replace_wikilinks(content: str) -> tuple[str, list[str]]:
    outlinks: list[str] = []

    def replace(match: re.Match) -> str:
        target, heading, alias = match.groups()
        target = target.strip()
        if target and target not in outlinks:
            outlinks.append(target)
        if alias:
            return alias.strip()
        if heading:
            return f"{target} > {heading.strip()}"
        return target

    return _WIKILINK_RE.sub(replace, content), outlinks


def parse_note(raw_text: str) -> tuple[str, dict]:
    """Parse an Obsidian note into (clean content, metadata).

    Metadata contains the frontmatter fields (minus reserved keys), the merged
    frontmatter + inline tags under "tags", and the wikilink targets under
    "outlinks". The content keeps wikilink text without brackets and drops
    image embeds.
    """
    post = frontmatter.loads(raw_text)
    content = post.content

    metadata = {
        key: value
        for key, value in post.metadata.items()
        if key not in RESERVED_METADATA_KEYS and key != "tags"
    }

    content = _strip_image_embeds(content)
    content, outlinks = _replace_wikilinks(content)

    tags = _normalize_tags(post.metadata.get("tags"))
    for tag in _INLINE_TAG_RE.findall(content):
        if tag not in tags:
            tags.append(tag)

    metadata["tags"] = tags
    metadata["outlinks"] = outlinks
    return content.strip(), metadata


class ObsidianConnector(SourceConnector):
    """Reads every markdown note of an Obsidian vault."""

    def __init__(self, vault_path: str | Path):
        self.vault_path = Path(vault_path)
        if not self.vault_path.is_dir():
            raise ValueError(f"Vault path is not a directory: {vault_path}")

    def _is_ignored(self, relative_path: Path) -> bool:
        return any(
            part in IGNORED_DIRS or part.startswith(".") for part in relative_path.parts[:-1]
        )

    def iter_documents(self) -> Iterator[SourceDocument]:
        for path in sorted(self.vault_path.rglob("*.md")):
            relative = path.relative_to(self.vault_path)
            if self._is_ignored(relative):
                continue

            content, metadata = parse_note(path.read_text(encoding="utf-8"))
            folder = relative.parent.as_posix()
            metadata.update(
                {
                    "note_path": relative.as_posix(),
                    "note_title": path.stem,
                    "folder": "" if folder == "." else folder,
                    "modified_at": datetime.fromtimestamp(path.stat().st_mtime).isoformat(
                        timespec="seconds"
                    ),
                }
            )
            yield SourceDocument(content=content, metadata=metadata)
