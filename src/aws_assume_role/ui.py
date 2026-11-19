"""
Terminal output and prompts: colored status lines, a spinner while waiting,
a summary panel for the credentials, and arrow-key prompts on a terminal.

Everything falls back to plain text when the output isn't a terminal (pipes,
tests, --credential-process on Windows) or uses a code page without the
symbols, such as the legacy Windows console.
"""

import contextlib
import getpass
import sys

try:
    from aws_assume_role import prompts
except ImportError:
    import prompts


def _console():
    # Created per call so redirected stdout (tests, --credential-process) is respected
    from rich.console import Console
    return Console(file=sys.stdout, soft_wrap=True, highlight=False)


def _unicode():
    encoding = (getattr(sys.stdout, 'encoding', None) or '').lower().replace('-', '')
    return encoding.startswith('utf')


def _symbol(fancy, plain):
    return fancy if _unicode() else plain


def _escape(text):
    from rich.markup import escape
    return escape(str(text))


def _line(symbol, style, message):
    _console().print("[%s]%s[/] %s" % (style, symbol, _escape(message)))


def banner(version=None):
    from rich.panel import Panel
    from rich.text import Text
    title = Text()
    title.append("olaar", style="bold cyan")
    title.append("  OneLogin %s AWS" % _symbol("→", "->"), style="bold")
    if version:
        title.append("  v%s" % version, style="dim")
    title.append("\nya-onelogin-aws-assume-role, an unofficial fork", style="dim")
    _console().print(Panel(title, border_style="cyan", expand=False))


def step(message):
    _line(_symbol("›", ">"), "cyan", message)


def ok(message):
    _line(_symbol("✔", "OK"), "bold green", message)


def warn(message):
    _line("!", "bold yellow", message)


def error(message):
    _line(_symbol("✖", "x"), "bold red", message)


def note(message):
    _console().print("[dim]%s[/]" % _escape(message))


@contextlib.contextmanager
def waiting(message):
    """
    Shows a spinner with message while the block runs, on a terminal;
    otherwise prints message once.
    """
    if prompts.menus_available():
        console = _console()
        with console.status(_escape(message), spinner="dots" if _unicode() else "line"):
            yield
    else:
        step(message)
        yield


def _ask(question):
    answer = question.ask()
    if answer is None:
        # Ctrl+C
        sys.exit(1)
    return answer


def ask_text(label, default=None):
    """
    Asks for a line of text. An empty answer returns default, when given.
    """
    if prompts.menus_available():
        try:
            import questionary
            answer = _ask(questionary.text(label, default=default or "", style=prompts.menu_style(), qmark="?"))
            return answer.strip() or default
        except SystemExit:
            raise
        except Exception:
            pass
    print("%s%s: " % (label, " (%s)" % default if default else ""))
    answer = prompts.read_line()
    return answer or default


def ask_password(label="OneLogin password"):
    if prompts.menus_available():
        try:
            import questionary
            return _ask(questionary.password(label, style=prompts.menu_style(), qmark="?"))
        except SystemExit:
            raise
        except Exception:
            pass
    return getpass.getpass("\n%s: " % label)


def confirm(question, default=True):
    """
    Asks a yes/no question and returns True for yes.
    """
    if prompts.menus_available():
        try:
            import questionary
            return _ask(questionary.confirm(question, default=default, style=prompts.menu_style(), qmark="?"))
        except SystemExit:
            raise
        except Exception:
            pass
    print("%s  (y/n)" % question)
    return prompts.get_yes_or_not() == 'y'


def summary(title, rows, style="green"):
    """
    Prints a panel with a two-column table of (label, value) rows.
    """
    from rich.panel import Panel
    from rich.table import Table
    table = Table.grid(padding=(0, 2))
    table.add_column(style="dim", no_wrap=True)
    table.add_column(overflow="fold")
    for label, value in rows:
        if value:
            table.add_row(label, _escape(value))
    _console().print(Panel(table, title="[bold %s]%s[/]" % (style, _escape(title)), title_align="left",
                           border_style=style, expand=False))


def table(title, headers, rows):
    """
    Prints a table with a title and column headers.
    """
    from rich.table import Table
    from rich import box
    table = Table(title=title, title_justify="left", title_style="bold", box=box.SIMPLE_HEAD, show_edge=False)
    for header in headers:
        table.add_column(header, overflow="fold")
    for row in rows:
        table.add_row(*[_escape(cell) for cell in row])
    _console().print(table)
