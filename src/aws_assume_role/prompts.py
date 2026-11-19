"""
Reads the user's answers to the CLI prompts.
"""

import sys


def read_line():
    """
    Reads the answer to a prompt. Exits once input runs out, since the callers
    re-prompt until they get a valid answer and would otherwise loop forever.
    """
    line = sys.stdin.readline()
    if not line:
        sys.exit("\nNo input to answer the prompt above: stdin reached end of file.")
    return line.strip()


def get_yes_or_not():
    answer = None
    while (answer != 'y' and answer != 'n'):
        answer = read_line().lower()
    return answer


def read_number(minimum, maximum):
    """
    Reads answers until one is a whole number from minimum to maximum.
    """
    while True:
        try:
            answer = int(read_line())
        except ValueError:
            continue
        if minimum <= answer <= maximum:
            return answer


def get_selection(max):
    return read_number(0, max - 1)


def get_duration():
    return read_number(900, 43200)


def ask_iteration_new_user():
    print("\nLog in as another user?  (y/n)")
    answer = get_yes_or_not()
    if answer == 'y':
        return True
    else:
        sys.exit()


# Arrow-key menus are used when both ends are a terminal, unless --no-menu
use_menus = True
SEPARATOR = "-----------------------------------------------------------------------"


def menus_available():
    if not use_menus:
        return False
    try:
        import questionary  # noqa: F401
    except ImportError:
        return False
    return sys.stdin.isatty() and sys.stdout.isatty()


def select_option(title, labels, default=None):
    """
    Asks the user to pick one of labels and returns its index. Shows an
    arrow-key menu with type-to-filter on a terminal, starting on default,
    otherwise the numbered list read by get_selection.
    """
    if len(labels) == 1:
        return 0
    if menus_available():
        try:
            return _select_with_menu(title, labels, default)
        except Exception as e:
            # e.g. a console prompt_toolkit can't drive; the numbered list still works
            print("(Menu not available: %s)" % e)
    print(SEPARATOR)
    for index, label in enumerate(labels):
        print(" %s | %s" % (index, label))
    print(SEPARATOR)
    hint = " (last time: %s)" % default if default is not None else ""
    print("\n%s [0-%s]%s: " % (title, len(labels) - 1, hint))
    return get_selection(len(labels))


def menu_style():
    import questionary
    return questionary.Style([
        ("qmark", "fg:ansicyan bold"),
        ("question", "bold"),
        ("pointer", "fg:ansicyan bold"),
        ("highlighted", "fg:ansicyan bold"),
        ("selected", "fg:ansicyan"),
        ("answer", "fg:ansigreen bold"),
        ("instruction", "fg:ansibrightblack"),
    ])


def _select_with_menu(title, labels, default):
    import questionary

    choices = [questionary.Choice(label, value=index) for index, label in enumerate(labels)]
    answer = questionary.select(
        title,
        choices=choices,
        default=choices[default] if default is not None and 0 <= default < len(choices) else None,
        use_search_filter=True,
        use_jk_keys=False,
        instruction="(arrows to move, type to filter, Enter to pick)",
        style=menu_style(),
        pointer=">",
    ).ask()
    if answer is None:
        # Ctrl+C
        sys.exit(1)
    return answer
