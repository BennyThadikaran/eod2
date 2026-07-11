from __future__ import annotations

from dataclasses import dataclass

from .dtypes import BreadthOption


@dataclass(slots=True)
class NavigationList:
    """Lightweight wrapper to navigate symbols lists"""

    items: list[str] | list[BreadthOption]
    length: int
    current_index: int = 0

    def current(self) -> str:
        """Return the current item."""
        return self.items[self.current_index]

    def next(self) -> str:
        """Move cursor forward, return new current item."""
        if self.can_go_next():
            self.current_index += 1
        return self.current()

    def previous(self) -> str:
        """Move cursor backward, return new current item."""
        if self.can_go_previous():
            self.current_index -= 1
        return self.current()

    def jump_to(self, index: int) -> bool:
        """
        Jump to the given 1-based index and return True on success

        Returns False if index is out of bounds
        """
        if not 1 <= index <= self.length:
            return False

        self.current_index = index - 1
        return True

    def can_go_next(self) -> bool:
        """Check if there is a next item."""
        return self.current_index < self.length - 1

    def can_go_previous(self) -> bool:
        """Check if there is a previous item."""
        return self.current_index > 0
