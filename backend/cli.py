import click
from flask import current_app
from flask.cli import AppGroup

from .models import User
from .rag import get_pipeline
from .rag.sync import sync_vault

obsidian_cli = AppGroup("obsidian", help="Obsidian vault commands.")


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
    user = User.query.filter_by(email=email.strip().lower()).first()
    if not user:
        raise click.ClickException(f"No user found with email {email!r}")

    pipeline = get_pipeline(
        persist_directory=current_app.config["VECTOR_STORE_FOLDER"],
        top_k=current_app.config["RAG_TOP_K"],
    )
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
