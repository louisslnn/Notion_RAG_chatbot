from collections import Counter

import click
from flask import current_app
from flask.cli import AppGroup

from .evals.generator import GoldsetGenerator
from .evals.goldset import save_goldset
from .models import User
from .rag import get_pipeline
from .rag.sync import sync_vault

obsidian_cli = AppGroup("obsidian", help="Obsidian vault commands.")
rag_cli = AppGroup("rag", help="RAG evaluation commands.")


def _require_user(email: str) -> User:
    user = User.query.filter_by(email=email.strip().lower()).first()
    if not user:
        raise click.ClickException(f"No user found with email {email!r}")
    return user


def _app_pipeline():
    return get_pipeline(
        persist_directory=current_app.config["VECTOR_STORE_FOLDER"],
        top_k=current_app.config["RAG_TOP_K"],
    )


@obsidian_cli.command("sync")
@click.option(
    "--vault",
    "vault_path",
    required=True,
    type=click.Path(exists=True, file_okay=False),
    help="Path to the Obsidian vault directory.",
)
@click.option("--user", "email", required=True, help="Email of the user owning the notes.")
@click.option("--dry-run", is_flag=True, help="List planned actions without writing anything.")
def sync_command(vault_path: str, email: str, dry_run: bool):
    """Sync an Obsidian vault into a user's knowledge base."""
    user = _require_user(email)
    pipeline = _app_pipeline()
    report = sync_vault(vault_path, user_id=user.id, pipeline=pipeline, dry_run=dry_run)

    if dry_run:
        click.echo("Dry run - nothing was written.")
        for verb, paths in (
            ("add", report.added),
            ("update", report.updated),
            ("delete", report.deleted),
        ):
            for path in paths:
                click.echo(f"  would {verb}: {path}")

    click.echo(
        f"{len(report.added)} new, {len(report.updated)} updated, "
        f"{len(report.deleted)} deleted, {report.unchanged} unchanged "
        f"({report.duration_seconds:.2f}s)"
    )


@rag_cli.command("generate-goldset")
@click.option(
    "--vault",
    "vault_path",
    required=True,
    type=click.Path(exists=True, file_okay=False),
    help="Path to the Obsidian vault directory.",
)
@click.option("--user", "email", required=True, help="Email of the vault owner.")
@click.option("--n", "count", default=60, show_default=True, help="Number of questions.")
@click.option("--out", "out_path", default="evals/goldset.draft.jsonl", show_default=True)
@click.option("--seed", default=42, show_default=True, help="Sampling seed (reproducibility).")
def generate_goldset_command(vault_path: str, email: str, count: int, out_path: str, seed: int):
    """Generate a DRAFT gold set from a vault (requires human validation)."""
    _require_user(email)

    generator = GoldsetGenerator()
    items = generator.generate(
        vault_path,
        count,
        seed=seed,
        on_progress=lambda done: click.echo(f"\r{done}/{count} questions", nl=False),
    )
    click.echo()
    save_goldset(items, out_path)

    by_tag = Counter(tag for item in items for tag in item.tags)
    click.echo(f"Wrote {len(items)} questions to {out_path} ({dict(by_tag)})")
    click.echo("This is a DRAFT: review every line by hand before renaming it goldset.jsonl.")
