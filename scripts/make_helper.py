#!/usr/bin/env python3
"""Helper script for prettier Makefile output using rich."""

import subprocess
import sys
import os
from pathlib import Path
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.panel import Panel
from rich import box

console = Console()


def get_indent_prefix(indent_level, is_last_line=False):
    """Get the tree-style prefix for the current indent level."""
    if indent_level == 0:
        return ""

    prefix = ""
    for i in range(indent_level):
        if i < indent_level - 1:
            prefix += "│ "
        else:
            prefix += "├─" if not is_last_line else "└─"
    return prefix


def get_continuing_prefix(indent_level):
    """Get the continuing tree line prefix for multi-line output."""
    if indent_level == 0:
        return ""
    return "│ " * indent_level


def run_task(name, cmd, show_output=False, allow_failure=False):
    """Run a task with a nice spinner and status indicator."""
    # Get current indent level from environment
    indent_level = int(os.environ.get("MAKE_INDENT_LEVEL", "0"))
    prefix = get_indent_prefix(indent_level)
    continuing = get_continuing_prefix(indent_level)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=not show_output,
    ) as progress:
        progress.add_task(f"{prefix}[cyan]{name}[/cyan]", total=None)

        # Pass incremented indent level to child processes
        new_env = os.environ.copy()
        new_env["MAKE_INDENT_LEVEL"] = str(indent_level + 1)

        if show_output:
            result = subprocess.run(cmd, shell=True, text=True, env=new_env)
        else:
            result = subprocess.run(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # Combine stderr with stdout
                text=True,
                env=new_env,
            )

        if result.returncode == 0:
            console.print(f"{prefix}[green]✓[/green] {name}")
            if show_output and hasattr(result, "stdout") and result.stdout:
                for line in result.stdout.strip().split("\n"):
                    console.print(f"{continuing}  {line}", style="dim")
        else:
            if allow_failure:
                console.print(
                    f"{prefix}[yellow]⚠[/yellow] {name} (non-critical failure)"
                )
            else:
                console.print(f"{prefix}[red]✗[/red] {name}")
                # Show full output on error, not in a panel to avoid truncation
                if hasattr(result, "stdout") and result.stdout:
                    console.print(f"{continuing}[red]Error output:[/red]")
                    for line in result.stdout.strip().split("\n"):
                        console.print(f"{continuing}  {line}", style="red dim")
                sys.exit(result.returncode)

        return result


def run_subtask(name, cmd):
    """Run a subtask with indented output."""
    # Get current indent level from environment
    indent_level = (
        int(os.environ.get("MAKE_INDENT_LEVEL", "0")) + 1
    )  # Subtasks get extra level
    prefix = get_indent_prefix(indent_level)
    continuing = get_continuing_prefix(indent_level)

    # Pass incremented indent level to child processes
    new_env = os.environ.copy()
    new_env["MAKE_INDENT_LEVEL"] = str(indent_level)

    result = subprocess.run(
        cmd,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=new_env,
    )

    if result.returncode == 0:
        console.print(f"{prefix}[green]✓[/green] {name}", style="dim")
    else:
        console.print(f"{prefix}[red]✗[/red] {name}", style="dim")
        # Show full output including stdout and stderr
        if result.stdout:
            console.print(f"{continuing}[red]Error details:[/red]")
            for line in result.stdout.strip().split("\n"):
                console.print(f"{continuing}  {line}", style="red dim")
        sys.exit(result.returncode)  # Exit on subtask failure
    return True


def section_header(title):
    """Print a nice section header."""
    # Get current indent level from environment
    indent_level = int(os.environ.get("MAKE_INDENT_LEVEL", "0"))
    prefix = get_continuing_prefix(indent_level)

    console.print()
    if indent_level > 0:
        # For nested sections, use a simpler format with tree line
        console.print(f"{prefix}[bold cyan]── {title} ──[/bold cyan]")
    else:
        # Top-level sections get the full rule
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
            console.print(
                "[red]Usage: make_helper.py stream <name> <command> [indent_level]"
            )
            sys.exit(1)
        name = sys.argv[2]

        # Check for indent level from environment or arguments
        env_indent = int(os.environ.get("MAKE_INDENT_LEVEL", "0"))

        # Check if there's an indent level specified in arguments
        if len(sys.argv) > 4 and sys.argv[-1].isdigit():
            indent_level = int(sys.argv[-1])
            cmd = " ".join(sys.argv[3:-1])
        else:
            indent_level = env_indent
            cmd = " ".join(sys.argv[3:])

        # Apply tree-style prefixes
        prefix = get_indent_prefix(indent_level)
        # For stream output, we want to show a tree line connecting to the parent
        # Even at level 0, we add a visual indicator
        if indent_level == 0:
            continuing = "│ "  # Always show a tree line for streamed output
        else:
            continuing = get_continuing_prefix(indent_level)

        console.print(f"{prefix}[cyan]▶[/cyan] {name}")

        # Set environment variable for nested calls
        new_env = os.environ.copy()
        new_env["MAKE_INDENT_LEVEL"] = str(indent_level + 1)

        # Always use Popen to process output line by line with proper indentation
        process = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
            env=new_env,
        )

        # Process output line by line with tree continuation
        for line in iter(process.stdout.readline, ""):
            if line:
                # Strip trailing newline but keep other whitespace
                line = line.rstrip("\n\r")
                if line:  # Only print non-empty lines
                    # Handle special cases like Docker's progress output
                    if line.startswith("#"):
                        # Docker build steps - add special formatting
                        console.print(f"{continuing}[dim] {line}[/dim]")
                    elif line.startswith("=>") or line.startswith(" =>"):
                        # Docker layer output
                        console.print(f"{continuing}[cyan] {line}[/cyan]")
                    else:
                        console.print(f"{continuing} {line}")

        process.wait()
        result_code = process.returncode

        if result_code != 0:
            console.print(f"{prefix}[red]✗[/red] {name} failed")
            sys.exit(result_code)

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
