from rich.console import Console
from rich.table import Table
from rich.box import ROUNDED, HEAVY, SIMPLE_HEAD
from rich.panel import Panel
from rich.text import Text
import pandas as pd

console = Console()

def print_header(title: str, subtitle: str = ""):
    """Prints a styled header with an optional subtitle."""
    text = Text()
    text.append(title, style="bold magenta")
    if subtitle:
        text.append(f" - {subtitle}", style="italic cyan")
    
    panel = Panel(
        text,
        box=ROUNDED,
        border_style="bright_blue",
        padding=(0, 1)
    )
    console.print(panel)

def print_section(title: str):
    """Prints a section divider with a title."""
    console.print(f"\n[bold yellow]=== {title} ===[/bold yellow]")

def display_dataframe(df: pd.DataFrame, title: str = None, columns: list = None, header_style: str = "bold cyan"):
    """Displays a pandas DataFrame as a Rich Table."""
    if df.empty:
        console.print(f"[italic dim]No data available for {title if title else 'table'}.[/italic dim]")
        return

    table = Table(
        title=title,
        box=SIMPLE_HEAD,
        header_style=header_style,
        expand=False,  # Don't force full width
        show_lines=False,
        padding=(0, 1)
    )

    display_cols = columns if columns else df.columns.tolist()
    
    # Configure columns
    for col in display_cols:
        if col in ["Breakdown", "Note"]:
            # Reduce ratio for long text columns
            table.add_column(col, ratio=1, overflow="fold")
        elif col in ["Player", "Name"]:
            # Ensure names don't wrap and stay readable
            table.add_column(col, style="bold green", no_wrap=True)
        elif col in ["Proj", "Actual", "Score"]:
            table.add_column(col, justify="right", style="bright_white", no_wrap=True)
        elif col == "Status":
            table.add_column(col, justify="center", no_wrap=True)
        elif col == "EV (Avg/Max)":
            table.add_column("EV", justify="center", no_wrap=True)
        elif col == "SB/CS":
            table.add_column("SB/C", justify="center", no_wrap=True)
        else:
            table.add_column(col, no_wrap=True)

    # Add rows
    for _, row in df.iterrows():
        row_data = []
        for col in display_cols:
            val = row.get(col, "-")
            
            # Formatting logic for values
            if isinstance(val, (float, int)):
                if col in ["Proj", "Actual", "Score"]:
                    val_str = f"{val:.2f}"
                    # Color coding based on value thresholds
                    if val >= 60:
                        row_data.append(f"[bold bright_green]{val_str}[/bold bright_green]")
                    elif val >= 40:
                        row_data.append(f"[green]{val_str}[/green]")
                    elif val <= 20:
                        row_data.append(f"[red]{val_str}[/red]")
                    else:
                        row_data.append(val_str)
                else:
                    row_data.append(str(val))
            else:
                # Add status color coding
                if col == "Status":
                    if "Final" in str(val):
                        row_data.append(f"[dim]{val}[/dim]")
                    elif "Live" in str(val) or "Top" in str(val) or "Bot" in str(val):
                        row_data.append(f"[bold red]● {val}[/bold red]")
                    else:
                        row_data.append(str(val))
                elif col == "Breakdown" or col == "Note":
                    # Convert structured chip list to readable text if needed
                    if isinstance(val, list):
                        parts = []
                        for c in val:
                            if isinstance(c, dict):
                                parts.append(f"{c['label']}: {c['value']}" if c.get('value') else c['label'])
                            else:
                                parts.append(str(c))
                        val_str = ', '.join(parts)
                    else:
                        val_str = str(val)
                    val_str = val_str.replace("SP Skill: +", "[bold green]SP Skill: +[/bold green]")
                    val_str = val_str.replace("Platoon: +", "[bold cyan]Platoon: +[/bold cyan]")
                    val_str = val_str.replace("BvP: +", "[bold yellow]BvP: +[/bold yellow]")
                    row_data.append(val_str)
                else:
                    row_data.append(str(val))
                    
        table.add_row(*row_data)

    console.print(table)

def print_narrative(text: str):
    """Prints a styled narrative box."""
    # Convert markdown-style **bold** to Rich style [bold]
    import re
    styled_text = re.sub(r'\*\*(.*?)\*\*', r'[bold cyan]\1[/bold cyan]', text)
    
    panel = Panel(
        styled_text,
        title="[bold yellow]Analyst Narrative[/bold yellow]",
        box=HEAVY,
        border_style="yellow",
        padding=(1, 1)
    )
    console.print(panel)

def print_info(text: str):
    """Prints a styled info message using Rich markup."""
    console.print(text)

def print_totals(label: str, metrics: dict):
    """Prints summary metrics in a clean line."""
    parts = [f"[bold white]{label}[/bold white]"]
    for k, v in metrics.items():
        parts.append(f"{k}: [bold cyan]{v}[/bold cyan]")
    console.print(" | ".join(parts))
