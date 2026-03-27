"""
gtaa - Genesys Transcript AI Analyzer CLI
"""
from __future__ import annotations

import sys
from datetime import date, datetime
from pathlib import Path
from typing import List, Optional, Tuple

import click
from dotenv import load_dotenv
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

load_dotenv()

console = Console()
err_console = Console(stderr=True)


def _parse_date(ctx, param, value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise click.BadParameter(f"Expected format YYYY-MM-DD, got: {value}")


@click.group()
@click.version_option("0.1.0", prog_name="gtaa")
def cli():
    """Genesys Transcript AI Analyzer -- download and analyze call transcripts with Gemini."""
    pass


# ---------------------------------------------------------------------------
# auth commands
# ---------------------------------------------------------------------------

@cli.group()
def auth():
    """Manage Genesys Cloud authentication."""
    pass


@auth.command("login")
@click.option("--config", "config_path", default=None, help="Path to custom config YAML.")
def auth_login(config_path: Optional[str]):
    """Authenticate with Genesys Cloud (OAuth2 Authorization Code)."""
    from gtaa.config.settings import get_settings, reset_settings
    from gtaa.auth.genesys import login

    reset_settings()
    settings = get_settings(config_path)

    if not settings.genesys.client_id or not settings.genesys.client_secret:
        err_console.print(
            "[red]Error:[/red] GENESYS_CLIENT_ID and GENESYS_CLIENT_SECRET must be set.\n"
            "Copy .env.example to .env and fill in your credentials."
        )
        sys.exit(1)

    try:
        token = login(settings.genesys)
        console.print(f"[green]OK[/green] Authentication successful.")
        console.print(f"  Region: [cyan]{settings.genesys.region}[/cyan]")
        console.print(f"  Token cached at: [dim]{Path.home() / '.gtaa' / 'tokens.json'}[/dim]")
    except Exception as e:
        err_console.print(f"[red]Authentication failed:[/red] {e}")
        sys.exit(1)


@auth.command("status")
def auth_status():
    """Show Genesys Cloud authentication status."""
    from gtaa.auth.genesys import get_token_status

    status = get_token_status()
    if status["authenticated"]:
        console.print(f"[green]OK Genesys: Authenticated[/green]")
        console.print(f"  Expires at: [cyan]{status['expires_at']}[/cyan]")
        console.print(f"  Refresh token: {'yes' if status['has_refresh_token'] else 'no'}")
    else:
        console.print(f"[yellow]XX Genesys: Not authenticated[/yellow]")
        console.print(f"  {status['message']}")


@auth.command("gcp-login")
@click.option("--key-file", "key_file", required=True,
              envvar="GOOGLE_APPLICATION_CREDENTIALS",
              type=click.Path(exists=True, dir_okay=False),
              help="Path to the service account JSON key file.")
@click.option("--project", "project_id", required=True, envvar="GOOGLE_CLOUD_PROJECT",
              help="GCP project ID (used as quota/billing project).")
def auth_gcp_login(key_file: str, project_id: str):
    """
    Configure Google Cloud authentication with a service account key file.

    \b
    Required IAM role on the service account:
      roles/aiplatform.user  (Vertex AI User)

    \b
    Example:
      gtaa auth gcp-login --key-file ~/keys/my-sa.json --project my-gcp-project
    """
    from gtaa.auth.gcp import GCPAuthManager, GCPAuthError

    mgr = GCPAuthManager()
    try:
        mgr.setup(key_file=key_file, project_id=project_id)
        status = mgr.get_status()
        console.print(f"[green]OK GCP authentication configured.[/green]")
        console.print(f"  Account: [cyan]{status.get('email', 'unknown')}[/cyan]")
        console.print(f"  Project: [cyan]{project_id}[/cyan]")
        console.print(f"  Key file: [dim]{status.get('key_file', key_file)}[/dim]")
        console.print(f"  Cached:  [dim]{Path.home() / '.gtaa' / 'gcp_credentials.json'}[/dim]")
    except GCPAuthError as e:
        err_console.print(f"[red]GCP setup failed:[/red] {e}")
        sys.exit(1)


@auth.command("gcp-status")
def auth_gcp_status():
    """Show Google Cloud authentication status."""
    from gtaa.auth.gcp import GCPAuthManager

    status = GCPAuthManager().get_status()
    if status["authenticated"]:
        console.print(f"[green]OK GCP: Configured[/green]")
        console.print(f"  Account: [cyan]{status['email']}[/cyan]")
        if status.get("quota_project_id"):
            console.print(f"  Project: [cyan]{status['quota_project_id']}[/cyan]")
        console.print(f"  Method:  [dim]{status['method']}[/dim]")
        console.print(f"  Key file: [dim]{status.get('key_file', 'n/a')}[/dim]")
    else:
        console.print(f"[yellow]XX GCP: Not configured[/yellow]")
        console.print(f"  {status['message']}")


@auth.command("gcp-logout")
def auth_gcp_logout():
    """Remove cached Google Cloud credentials."""
    from gtaa.auth.gcp import GCPAuthManager, CACHE_PATH

    GCPAuthManager().logout()
    console.print(f"[green]OK GCP credentials cache removed.[/green]")
    console.print(f"  Deleted: [dim]{CACHE_PATH}[/dim]")


# ---------------------------------------------------------------------------
# analyze command
# ---------------------------------------------------------------------------

@cli.command("analyze")
@click.option("--start-date", required=True, callback=_parse_date, help="Start date (YYYY-MM-DD).")
@click.option("--end-date", required=True, callback=_parse_date, help="End date (YYYY-MM-DD).")
@click.option("--queue", "queue_ids", multiple=True, help="Queue ID to filter (can be repeated).")
@click.option("--agent", "user_ids", multiple=True, help="Agent user ID to filter (can be repeated).")
@click.option("--division", "division_ids", multiple=True, help="Division ID to filter (can be repeated).")
@click.option("--min-duration", "min_duration_seconds", default=None, type=int, help="Minimum call duration in seconds.")
@click.option("--prompt", "prompt_text", default=None, help="Analysis prompt text.")
@click.option("--prompt-file", "prompt_file", default=None, type=click.Path(exists=True), help="Path to file containing the analysis prompt.")
@click.option(
    "--output-format", "output_formats",
    multiple=True,
    type=click.Choice(["csv", "json", "excel", "pdf"], case_sensitive=False),
    default=["csv"],
    show_default=True,
    help="Output format(s). Can be repeated.",
)
@click.option("--output-dir", default="./output", show_default=True, help="Directory for output files.")
@click.option("--batch-size", default=20, show_default=True, help="Conversations per batch.")
@click.option("--max-workers", default=5, show_default=True, help="Concurrent processing workers.")
@click.option("--config", "config_path", default=None, help="Path to custom config YAML.")
@click.option("--dry-run", is_flag=True, default=False, help="List matching conversations without processing.")
def analyze(
    start_date: date,
    end_date: date,
    queue_ids: Tuple[str, ...],
    user_ids: Tuple[str, ...],
    division_ids: Tuple[str, ...],
    min_duration_seconds: Optional[int],
    prompt_text: Optional[str],
    prompt_file: Optional[str],
    output_formats: Tuple[str, ...],
    output_dir: str,
    batch_size: int,
    max_workers: int,
    config_path: Optional[str],
    dry_run: bool,
):
    """Download and analyze Genesys call transcripts with Vertex AI Gemini."""
    from gtaa.config.settings import get_settings, reset_settings
    from gtaa.auth.genesys import get_access_token
    from gtaa.auth.google import init_vertex_ai
    from gtaa.auth.gcp import GCPAuthManager, GCPAuthError
    from gtaa.genesys.client import build_api_client
    from gtaa.genesys.conversations import query_conversations, ConversationFilter
    from gtaa.processor.gemini import GeminiProcessor
    from gtaa.processor.batch import process_conversations
    from gtaa.output import write_outputs

    reset_settings()
    settings = get_settings(config_path)

    # Override batch/workers from CLI flags
    settings.processing.batch_size = batch_size
    settings.processing.max_workers = max_workers

    # Resolve prompt
    user_prompt = ""
    if prompt_file:
        user_prompt = Path(prompt_file).read_text(encoding="utf-8").strip()
    elif prompt_text:
        user_prompt = prompt_text.strip()
    else:
        user_prompt = "Summarize the main topic and outcome of this call in 2-3 sentences."
        console.print(f"[dim]No prompt provided -- using default: \"{user_prompt}\"[/dim]")

    # --- Validate Genesys credentials ---
    if not settings.genesys.client_id or not settings.genesys.client_secret:
        err_console.print(
            "[red]Error:[/red] Genesys credentials not set. "
            "Run `gtaa auth login` or set GENESYS_CLIENT_ID / GENESYS_CLIENT_SECRET."
        )
        sys.exit(1)

    # --- Genesys auth ---
    console.print(f"Connecting to Genesys Cloud [cyan]{settings.genesys.region}[/cyan]...")
    try:
        access_token = get_access_token(settings.genesys)
    except Exception as e:
        err_console.print(f"[red]Genesys auth error:[/red] {e}")
        sys.exit(1)

    api_client = build_api_client(access_token, settings.genesys)

    # --- Query conversations ---
    filters = ConversationFilter(
        start_date=start_date,
        end_date=end_date,
        queue_ids=list(queue_ids),
        user_ids=list(user_ids),
        division_ids=list(division_ids),
        min_duration_seconds=min_duration_seconds,
    )

    console.print(f"Querying conversations from [cyan]{start_date}[/cyan] to [cyan]{end_date}[/cyan]...")

    with console.status("Fetching conversation list..."):
        conversations = list(query_conversations(api_client, filters, settings.genesys))

    if not conversations:
        console.print("[yellow]No conversations found for the given filters.[/yellow]")
        sys.exit(0)

    console.print(f"Found [green]{len(conversations)}[/green] conversations.")

    if dry_run:
        _show_conversations_table(conversations)
        sys.exit(0)

    # --- GCP user credentials ---
    if not settings.google.project_id:
        err_console.print(
            "[red]Error:[/red] Google Cloud project ID not set. "
            "Set GOOGLE_CLOUD_PROJECT env var or 'google.project_id' in config."
        )
        sys.exit(1)

    gcp_auth = GCPAuthManager()
    try:
        gcp_credentials = gcp_auth.get_credentials()
        gcp_status = gcp_auth.get_status()
        console.print(
            f"Initializing Vertex AI as [cyan]{gcp_status.get('email', 'unknown')}[/cyan] "
            f"(project: [cyan]{settings.google.project_id}[/cyan])..."
        )
    except GCPAuthError as e:
        err_console.print(
            f"[red]GCP authentication required.[/red]\n"
            f"Run: [cyan]gtaa auth gcp-login --key-file path/to/sa.json --project {settings.google.project_id}[/cyan]\n"
            f"Details: {e}"
        )
        sys.exit(1)

    init_vertex_ai(settings.google.project_id, settings.google.location, credentials=gcp_credentials)
    gemini = GeminiProcessor(settings.google)

    # --- Process ---
    results = []
    formats_list = list(output_formats) or settings.output.default_formats

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Analyzing transcripts...", total=len(conversations))

        def on_progress(completed: int, total: int, result):
            status = "[green]OK[/green]" if not result.error else "[yellow]!![/yellow]"
            progress.update(task, advance=1, description=f"Analyzing... {status} {result.conversation_id[:8]}")

        for result in process_conversations(
            api_client=api_client,
            conversations=conversations,
            gemini=gemini,
            user_prompt=user_prompt,
            settings=settings.processing,
            progress_callback=on_progress,
        ):
            results.append(result)

    # --- Write output ---
    base_filename = f"analysis_{start_date}_{end_date}"
    created_files = write_outputs(results, formats_list, output_dir, base_filename)

    console.print(f"\n[green]OK Analysis complete.[/green] {len(results)} conversations processed.")
    for f in created_files:
        console.print(f"  [dim]->[/dim] [cyan]{f}[/cyan]")

    errors = [r for r in results if r.error]
    if errors:
        console.print(f"\n[yellow]Warning:[/yellow] {len(errors)} conversation(s) had errors.")


def _show_conversations_table(conversations):
    table = Table(title="Matching Conversations (dry run)", show_lines=False)
    table.add_column("Conversation ID", style="cyan", no_wrap=True)
    table.add_column("Start Time")
    table.add_column("Duration")
    table.add_column("Queue ID")

    for c in conversations[:50]:
        duration = f"{c.duration_ms // 60000}m {(c.duration_ms % 60000) // 1000}s"
        table.add_row(
            c.conversation_id,
            c.start_time.strftime("%Y-%m-%d %H:%M") if c.start_time else "",
            duration,
            c.queue_id or "",
        )

    console.print(table)
    if len(conversations) > 50:
        console.print(f"[dim]... and {len(conversations) - 50} more.[/dim]")


# ---------------------------------------------------------------------------
# demo command
# ---------------------------------------------------------------------------

@cli.command("demo")
@click.option(
    "--prompt", "prompt_text",
    default=None,
    help="Analysis prompt. Defaults to a summary prompt.",
)
@click.option(
    "--prompt-file", "prompt_file",
    default=None,
    type=click.Path(exists=True),
    help="Path to file containing the analysis prompt.",
)
@click.option(
    "--output-format", "output_formats",
    multiple=True,
    type=click.Choice(["csv", "json", "excel", "pdf"], case_sensitive=False),
    default=["csv", "json"],
    show_default=True,
    help="Output format(s). Can be repeated.",
)
@click.option("--output-dir", default="./output/demo", show_default=True, help="Directory for output files.")
@click.option(
    "--sample", "sample_ids",
    multiple=True,
    type=click.Choice(["1", "2", "3", "4", "5"]),
    help="Sample transcript IDs to run (1-5). Default: all.",
)
@click.option("--list-samples", is_flag=True, default=False, help="List available sample transcripts and exit.")
@click.option("--show-transcript", is_flag=True, default=False, help="Print the transcript text before analysis.")
@click.option("--config", "config_path", default=None, help="Path to custom config YAML.")
def demo(
    prompt_text: Optional[str],
    prompt_file: Optional[str],
    output_formats: Tuple[str, ...],
    output_dir: str,
    sample_ids: Tuple[str, ...],
    list_samples: bool,
    show_transcript: bool,
    config_path: Optional[str],
):
    """
    Run AI analysis on built-in sample Genesys transcripts (no credentials needed).

    \b
    Includes 5 realistic call center scenarios:
      1. Billing dispute (bank)
      2. Technical support - internet outage
      3. Customer retention - cancellation attempt
      4. Healthcare appointment rescheduling
      5. E-commerce damaged product complaint
    """
    from gtaa.demo.sample_transcripts import (
        SAMPLE_TRANSCRIPT_JSONS,
        build_sample_conversations,
        build_sample_transcripts,
    )
    from gtaa.config.settings import get_settings, reset_settings
    from gtaa.auth.google import init_vertex_ai
    from gtaa.auth.gcp import GCPAuthManager, GCPAuthError
    from gtaa.processor.gemini import GeminiProcessor, AnalysisResult
    from gtaa.output import write_outputs

    if list_samples:
        _list_samples_table(SAMPLE_TRANSCRIPT_JSONS)
        return

    reset_settings()
    settings = get_settings(config_path)

    # Resolve prompt
    if prompt_file:
        user_prompt = Path(prompt_file).read_text(encoding="utf-8").strip()
    elif prompt_text:
        user_prompt = prompt_text.strip()
    else:
        user_prompt = "Summarize the main issue or reason for this call and its outcome in 2-3 sentences."
        console.print(f"[dim]Using default prompt: \"{user_prompt}\"[/dim]\n")

    # Filter samples
    all_convs = build_sample_conversations()
    all_transcripts = build_sample_transcripts()

    if sample_ids:
        indices = [int(sid) - 1 for sid in sample_ids]
        selected_convs = [all_convs[i] for i in indices if i < len(all_convs)]
        selected_transcripts = [all_transcripts[i] for i in indices if i < len(all_transcripts)]
    else:
        selected_convs = all_convs
        selected_transcripts = all_transcripts

    console.print(f"Running demo on [green]{len(selected_convs)}[/green] sample transcript(s).\n")

    if show_transcript:
        _print_transcripts(selected_convs, selected_transcripts)

    # --- GCP user credentials ---
    if not settings.google.project_id:
        err_console.print(
            "[red]Error:[/red] Google Cloud project ID not set.\n"
            "Set [cyan]GOOGLE_CLOUD_PROJECT[/cyan] env var or 'google.project_id' in config.\n\n"
            "To set up GCP authentication run:\n"
            "  [cyan]gtaa auth gcp-login --project YOUR_PROJECT_ID[/cyan]\n\n"
            "You can still explore transcripts without GCP:\n"
            "  [cyan]gtaa demo --list-samples[/cyan]\n"
            "  [cyan]gtaa demo --show-transcript[/cyan]"
        )
        sys.exit(1)

    gcp_auth = GCPAuthManager()
    try:
        gcp_credentials = gcp_auth.get_credentials()
        gcp_status = gcp_auth.get_status()
        console.print(
            f"Vertex AI as [cyan]{gcp_status.get('email', 'unknown')}[/cyan] "
            f"(project: [cyan]{settings.google.project_id}[/cyan])..."
        )
    except GCPAuthError as e:
        err_console.print(
            f"[red]GCP authentication required.[/red]\n"
            f"Run: [cyan]gtaa auth gcp-login --key-file path/to/sa.json --project {settings.google.project_id}[/cyan]\n"
            f"Details: {e}"
        )
        sys.exit(1)

    try:
        init_vertex_ai(settings.google.project_id, settings.google.location, credentials=gcp_credentials)
    except Exception as e:
        err_console.print(f"[red]Vertex AI init error:[/red] {e}")
        sys.exit(1)

    gemini = GeminiProcessor(settings.google)

    results: List[AnalysisResult] = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task_bar = progress.add_task("Analyzing...", total=len(selected_convs))

        for conv, transcript in zip(selected_convs, selected_transcripts):
            progress.update(task_bar, description=f"Analyzing: [cyan]{conv.queue_name}[/cyan]")
            result = gemini.analyze(
                conversation=conv,
                transcript=transcript,
                user_prompt=user_prompt,
                max_transcript_chars=settings.processing.max_transcript_chars,
            )
            results.append(result)
            progress.advance(task_bar)

    # --- Print results to console ---
    console.print()
    _print_results_table(results)

    # --- Write output ---
    formats_list = list(output_formats)
    base_filename = "demo_analysis"
    created_files = write_outputs(results, formats_list, output_dir, base_filename)

    console.print(f"\n[green]OK Done.[/green] Output files:")
    for f in created_files:
        console.print(f"  [dim]->[/dim] [cyan]{f}[/cyan]")


def _list_samples_table(sample_jsons: list):
    from rich.table import Table as RichTable
    table = RichTable(title="Available Sample Transcripts", show_lines=True)
    table.add_column("#", style="bold cyan", width=3)
    table.add_column("Queue / Scenario", style="green")
    table.add_column("Duration", justify="right")
    table.add_column("Conversation ID", style="dim")

    for i, item in enumerate(sample_jsons, 1):
        meta = item["_conversation_meta"]
        dur_s = meta["duration_ms"] // 1000
        table.add_row(
            str(i),
            meta["queue"],
            f"{dur_s // 60}m {dur_s % 60}s",
            meta["conversation_id"],
        )
    console.print(table)


def _print_transcripts(conversations, transcripts):
    from rich.panel import Panel
    from rich.text import Text

    for conv, transcript in zip(conversations, transcripts):
        lines = Text()
        for turn in transcript.turns:
            role = turn.speaker_role.upper()
            color = "green" if turn.speaker_role == "agent" else "cyan"
            lines.append(f"{role}: ", style=f"bold {color}")
            lines.append(f"{turn.text}\n")
        console.print(Panel(lines, title=f"[bold]{conv.queue_name}[/bold] -- {conv.conversation_id[:8]}"))
        console.print()


def _print_results_table(results: list):
    from rich.panel import Panel

    for result in results:
        status = "[green]OK[/green]" if not result.error else "[yellow]!![/yellow]"
        title = f"{status} [bold]{result.queue_name or result.conversation_id[:8]}[/bold] ({result.duration_formatted})"
        console.print(Panel(result.analysis, title=title, border_style="green" if not result.error else "yellow"))
        console.print()


if __name__ == "__main__":
    cli()
