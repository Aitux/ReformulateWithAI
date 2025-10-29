"""Terminal progress helpers used by the Reformulator CLI."""

from __future__ import annotations

import os
import sys
from typing import List


ASCII_LOGO = (
    "                                                                                                                  %%%%%%%%%                                               \n"
    "                                                                                                                 %%%%%%%%%%%%                                             \n"
    "                                                                                                                %%%%%%%%%%%%%%                                            \n"
    "                                                                                                               %%%%%%%%% %%%%%%                                           \n"
    "                                                                                                              %%%%%%%%%   %%%%%%                                          \n"
    "                                              @@@        @@@         @@         @@@        @@@       @@@     %%%%%% %%%   %%%%%%                                          \n"
    "                                            @@@@@@@    @@@@@@@     @@@@@@@    @@@@@@@    @@@@@@@   @@@@@@@   %%%%%  %%%   %%%%%%                                          \n"
    "                                           @@@@@@@@@  @@@@@@@@@   @@@@@@@@@  @@@@@@@@@  @@@@@@@@@ @@@@@@@@@  %%%%%%%%%%     %%%%%                                         \n"
    "                                          @@@@   @@@  @@@   @@@@ @@@@   @@@ @@@@   @@@@@@@@   @@@@@@@   @@@ %%%%%%%%%%%      %%%%                                         \n"
    "                                          @@@     @@@@@@     @@@ @@@     @@ @@@     @@@@@@@       @@@       %%%%%%%%%%%     %%%%%                                         \n"
    "                                          @@      @@@@@@        @@@         @@@@@@@@@@@ @@@@@@@   @@@@@@@@  %%%%%%  %%%   %%%%%%%                                         \n"
    "                                          @@      @@@@@@        @@@         @@@@@@@@@@@  @@@@@@@   @@@@@@@@ %%%%%%  %%%   %%%%%%%                                         \n"
    "                                          @@@     @@@@@@     @@@ @@@     @@ @@@              @@@@      @@@@  %%%%%  %%%   %%%%%%%                                         \n"
    "                                          @@@@  @@@@@ @@@   @@@@ @@@@   @@@ @@@@   @@@  @@    @@@ @@    @@@  %%%%%  %%%   %%%%%%                                          \n"
    "                                           @@@@@@@@@@ @@@@@@@@@   @@@@@@@@@  @@@@@@@@@ @@@@@@@@@@@@@@@@@@@@  %%%%%  %%%   %%%%%%                                          \n"
    "                                            @@@@@@@@@  @@@@@@@    @@@@@@@@    @@@@@@@   @@@@@@@@  @@@@@@@@    %%%%%%%%%%%%%%%%%                                           \n"
    "                                              @@@  @     @@@        @@@        @@@@       @@@@      @@@@       %%%%%%%%%%%%%%%%                                           \n"
    "                                                                                                                %%%%%%%%%%%%%%                                            \n"
    "                                                                                                                 %%%%%%%%%%%%                                             \n"
    "                                                                                                                  %%%%%%%%%                                               "
)

ASCII_LOGO_LINES: List[str] = ASCII_LOGO.splitlines()
ASCII_LOGO_TOTAL_CHARS = sum(len(line) for line in ASCII_LOGO_LINES)
STDOUT_IS_TTY = sys.stdout.isatty()


def clear_terminal() -> None:
    """Clear the current terminal when possible."""
    if not STDOUT_IS_TTY:
        return
    if os.name == "nt":
        os.system("cls")
    else:
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()


def print_banner(*, flush: bool = True) -> None:
    """Print the application banner."""
    print(f"{ASCII_LOGO}\n", end="", flush=flush)


def build_logo_progress(ratio: float) -> str:
    """Return an ASCII logo partially revealed according to the provided ratio."""
    if ASCII_LOGO_TOTAL_CHARS <= 0 or not ASCII_LOGO_LINES:
        return ""
    clamped_ratio = max(0.0, min(1.0, ratio))
    visible_chars = int(ASCII_LOGO_TOTAL_CHARS * clamped_ratio)
    if clamped_ratio > 0.0 and visible_chars == 0:
        visible_chars = 1
    visible_chars = min(ASCII_LOGO_TOTAL_CHARS, visible_chars)
    remaining = visible_chars
    rendered_lines: List[str] = []
    for line in ASCII_LOGO_LINES:
        line_length = len(line)
        if remaining <= 0:
            rendered_lines.append(" " * line_length)
            continue
        if remaining >= line_length:
            rendered_lines.append(line)
            remaining -= line_length
            continue
        rendered_lines.append(line[:remaining] + " " * (line_length - remaining))
        remaining = 0
    return "\n".join(rendered_lines)


def refresh_progress_display(progress_line: str) -> None:
    """Render the progress banner + status line."""
    if not STDOUT_IS_TTY:
        print(progress_line, flush=True)
        return
    clear_terminal()
    print(progress_line, flush=True)


__all__ = [
    "ASCII_LOGO",
    "build_logo_progress",
    "clear_terminal",
    "print_banner",
    "refresh_progress_display",
]
