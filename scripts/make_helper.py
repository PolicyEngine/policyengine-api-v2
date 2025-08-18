#!/usr/bin/env python3
"""Helper script for prettier Makefile output using rich."""

import subprocess
import sys
import time
from pathlib import Path
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.panel import Panel
from rich.table import Table
from rich import box

console = Console()


def run_task(name, cmd, show_output=False, allow_failure=False):
    """Run a task with a nice spinner and status indicator."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=not show_output,
    ) as progress:
        task = progress.add_task(f"[cyan]{name}[/cyan]", total=None)

        if show_output:
            result = subprocess.run(cmd, shell=True, text=True)
        else:
            result = subprocess.run(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # Combine stderr with stdout
                text=True,
            )

        if result.returncode == 0:
            console.print(f"[green]✓[/green] {name}")
            if show_output and hasattr(result, "stdout") and result.stdout:
                console.print(result.stdout, style="dim")
        else:
            if allow_failure:
                console.print(f"[yellow]⚠[/yellow] {name} (non-critical failure)")
            else:
                console.print(f"[red]✗[/red] {name}")
                # Show full output on error, not in a panel to avoid truncation
                if hasattr(result, "stdout") and result.stdout:
                    console.print("\n[red]Error output:[/red]")
                    console.print(result.stdout, style="red dim")
                sys.exit(result.returncode)

        return result


def run_subtask(name, cmd):
    """Run a subtask with indented output."""
    result = subprocess.run(
        cmd,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    if result.returncode == 0:
        console.print(f"  [green]✓[/green] {name}", style="dim")
    else:
        console.print(f"  [red]✗[/red] {name}", style="dim")
        # Show full output including stdout and stderr
        if result.stdout:
            console.print("\n[red]  Error details:[/red]")
            for line in result.stdout.strip().split("\n"):
                console.print(f"    {line}", style="red dim")
        sys.exit(result.returncode)  # Exit on subtask failure
    return True


def section_header(title):
    """Print a nice section header."""
    console.print()
    console.rule(f"[bold cyan]{title}[/bold cyan]", style="cyan")


def completion_message(message, success=True):
    """Print a completion message."""
    style = "green" if success else "red"
    icon = "✓" if success else "✗"
    console.print()
    console.print(
        Panel(
            f"[{style}]{icon}[/{style}] {message}",
            border_style=style,
            box=box.ROUNDED,
        )
    )


def list_items(items, title=None):
    """Print a list of items."""
    if title:
        console.print(f"\n[bold]{title}:[/bold]")
    for item in items:
        console.print(f"  • {item}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        console.print("[red]Usage: make_helper.py <command> [args...]")
        sys.exit(1)

    command = sys.argv[1]

    if command == "task":
        # Run a single task
        if len(sys.argv) < 4:
            console.print("[red]Usage: make_helper.py task <name> <command>")
            sys.exit(1)
        name = sys.argv[2]
        cmd = " ".join(sys.argv[3:])
        run_task(name, cmd)

    elif command == "subtask":
        # Run a subtask (indented)
        if len(sys.argv) < 4:
            console.print("[red]Usage: make_helper.py subtask <name> <command>")
            sys.exit(1)
        name = sys.argv[2]
        cmd = " ".join(sys.argv[3:])
        run_subtask(name, cmd)

    elif command == "section":
        # Print a section header
        if len(sys.argv) < 3:
            console.print("[red]Usage: make_helper.py section <title>")
            sys.exit(1)
        title = " ".join(sys.argv[2:])
        section_header(title)

    elif command == "complete":
        # Print completion message
        if len(sys.argv) < 3:
            console.print("[red]Usage: make_helper.py complete <message> [success]")
            sys.exit(1)
        message = sys.argv[2]
        success = sys.argv[3].lower() == "true" if len(sys.argv) > 3 else True
        completion_message(message, success)

    elif command == "list":
        # List items
        if len(sys.argv) < 3:
            console.print("[red]Usage: make_helper.py list <item1> <item2> ...")
            sys.exit(1)
        items = sys.argv[2:]
        list_items(items)

    elif command == "stream":
        # Run a command with streaming output
        if len(sys.argv) < 4:
            console.print("[red]Usage: make_helper.py stream <name> <command>")
            sys.exit(1)
        name = sys.argv[2]
        cmd = " ".join(sys.argv[3:])
        console.print(f"[cyan]▶[/cyan] {name}")
        # Run without capturing output to allow streaming
        result = subprocess.run(cmd, shell=True)
        if result.returncode != 0:
            console.print(f"[red]✗[/red] {name} failed")
            sys.exit(result.returncode)

    elif command == "progress":
        # Run command with progress bar for multiple subdirectories
        if len(sys.argv) < 4:
            console.print("[red]Usage: make_helper.py progress <title> <dirs...>")
            sys.exit(1)
        title = sys.argv[2]
        dirs = sys.argv[3:]

        with Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=console,
        ) as progress:
            task = progress.add_task(f"[cyan]{title}[/cyan]", total=len(dirs))

            failed = []
            for dir_name in dirs:
                dir_base = Path(dir_name).name
                progress.update(task, description=f"[cyan]{title}[/cyan] - {dir_base}")

                # Extract the actual make command from the directory
                make_cmd = f"$(MAKE) -C {dir_name} {title.lower().replace(' ', '-')}"
                result = subprocess.run(
                    make_cmd, shell=True, capture_output=True, text=True
                )

                if result.returncode != 0:
                    failed.append(dir_base)

                progress.advance(task)

            if failed:
                console.print(f"\n[red]Failed in: {', '.join(failed)}[/red]")
                sys.exit(1)
            else:
                console.print(f"\n[green]✓[/green] {title} completed successfully")

    else:
        console.print(f"[red]Unknown command: {command}")
        sys.exit(1)
