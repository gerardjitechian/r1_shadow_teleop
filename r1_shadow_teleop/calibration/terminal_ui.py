import sys
import time

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import BarColumn, Progress, TextColumn, TimeRemainingColumn
except ImportError:
    Console = None
    Panel = None
    Progress = None
    BarColumn = None
    TextColumn = None
    TimeRemainingColumn = None


class TerminalUI:
    def __init__(self, stream=None, use_rich=True):
        self.stream = stream or sys.stdout
        self.console = None
        if (
            use_rich
            and Console is not None
            and hasattr(self.stream, "isatty")
            and self.stream.isatty()
        ):
            self.console = Console()

    def write(self, message=""):
        if self.console is not None:
            self.console.print(message)
        else:
            print(message)

    def rule(self, title: str):
        if self.console is not None:
            self.console.rule(title)
            return
        print()
        print(title)
        print("=" * len(title))

    def panel(self, title: str, lines):
        body = "\n".join(lines)
        if self.console is not None and Panel is not None:
            self.console.print(Panel(body, title=title))
            return
        self.rule(title)
        print(body)

    def warning(self, message: str):
        if self.console is not None:
            self.console.print(f"[yellow]warning:[/] {message}")
        else:
            print(f"warning: {message}")

    def progress(self, label: str, seconds: float, sleep_fn=time.sleep):
        run_timed_progress(label, seconds, self, sleep_fn=sleep_fn)


def terminal_ui() -> TerminalUI:
    return TerminalUI()


def run_timed_progress(
    label: str,
    seconds: float,
    ui: TerminalUI,
    sleep_fn=time.sleep,
    tick_seconds: float = 0.1,
):
    duration = max(0.0, float(seconds))
    if duration <= 0.0:
        ui.write(f"{label} for 0.0s...")
        return

    if ui.console is None or Progress is None:
        ui.write(f"{label} for {duration:.1f}s...")
        sleep_fn(duration)
        return

    progress = Progress(
        TextColumn("{task.description}"),
        BarColumn(),
        TextColumn("{task.percentage:>3.0f}%"),
        TimeRemainingColumn(),
        console=ui.console,
        transient=True,
    )
    elapsed = 0.0
    with progress:
        task = progress.add_task(f"{label} ({duration:.1f}s)", total=duration)
        while elapsed < duration:
            step = min(tick_seconds, duration - elapsed)
            sleep_fn(step)
            elapsed += step
            progress.update(task, completed=elapsed)
