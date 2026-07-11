from __future__ import annotations

from pathlib import Path
from typing import Any

from .dtypes import Timeframe
from .util import load_json, write_json


class SessionStore:
    """Reads/writes session state to JSON files.

    Manages:
    - Watch resume state (current symbol index)
    - Drawing persistence (data/drawings.json)
    - Selections persistence (selections.csv)
    """

    def __init__(
        self,
        user_config_path: Path,
        drawings_path: Path,
        selections_path: Path,
        timeframe: Timeframe,
    ) -> None:
        """Initialize session store with file paths.

        Args:
            user_config_path: Path to session JSON file for watch resume state
            drawings_path: Path to data/drawings.json
            selections_path: Path to selections.csv
        """
        self._user_config_path: Path = user_config_path
        self._drawings_path: Path = drawings_path
        self._selections_path: Path = selections_path
        self.selections: set[str] = set()
        self._timeframe: Timeframe = timeframe

    def save_watch_resume(self, watch_name: str, index: int) -> None:
        """Save watch resume state.

        Args:
            watch_name: Name of the watchlist
            index: Current symbol index
        """
        data = load_json(self._user_config_path)

        data.setdefault("CHART_RESUME", {})

        data["CHART_RESUME"][watch_name] = index
        write_json(self._user_config_path, data)

    def save_drawings(self, drawings: dict[str, dict[str, Any]]) -> None:
        """Save drawings for the current timeframe.

        Args:
            drawings: Dict shaped as symbol -> url -> Drawing dict.

        File shape:
            timeframe -> symbol -> url -> Drawing dict
        """
        self._drawings_path.parent.mkdir(parents=True, exist_ok=True)

        if self._drawings_path.is_file():
            data = load_json(self._drawings_path)
        else:
            data = {}

        data[self._timeframe] = drawings

        write_json(self._drawings_path, data)

    def load_drawings(self) -> dict[str, dict[str, Any]]:
        """Load drawings for the current timeframe.

        Returns:
            Dict shaped as symbol -> url -> Drawing dict.
            Returns an empty dict if the file or timeframe does not exist.
        """
        if not self._drawings_path.is_file():
            return {}

        data = load_json(self._drawings_path)

        return data.get(self._timeframe, {})

    def save_selections(self, symbols: set[str]) -> None:
        """Save selected symbols to selections.csv.

        Args:
            symbols: Set of selected symbol names
        """
        content = "\n".join(sorted(symbols))
        self._selections_path.write_text(content, encoding="utf-8")
