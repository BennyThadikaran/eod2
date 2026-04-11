from typing import List, Dict, Optional, TypedDict, Literal, cast
from datetime import date
from pathlib import Path
import json


class SymbolHistory(TypedDict):
    """
    Represents the historical record of a symbol mapped to an ISIN.

    Attributes:
        symbol (str): The trading symbol associated with the ISIN.
        from_date (date): The start date from which the symbol is valid.
        to_date (date): The end date until which the symbol is valid.
        action (Optional[str]): Optional metadata describing an action
            (e.g., symbol change, merger, etc.) affecting this record.
    """

    symbol: str
    from_date: date
    to_date: date
    action: Optional[str]


class SymbolISINMap(TypedDict):
    """
    Container for symbol-to-ISIN mappings and their historical records.

    Attributes:
        sym2isin (Dict[str, str]): Maps a symbol to its corresponding ISIN.
        isin2hist (Dict[str, List[SymbolHistory]]): Maps an ISIN to its
            chronological list of symbol history entries.
    """

    sym2isin: Dict[str, str]
    isin2hist: Dict[str, List[SymbolHistory]]


class SymbolTracker:
    """
    Tracks and maintains the relationship between trading symbols and ISINs
    over time, including historical changes.

    This class allows updating symbol-ISIN mappings, retrieving the latest
    symbol for a given ISIN or symbol, accessing full history, and
    serializing/deserializing the data to and from JSON.
    """

    def __init__(self, data_file: Optional[Path] = None) -> None:
        """
        Initializes the SymbolTracker.

        Args:
            data_file (Optional[Path]): Path to a JSON file containing previously
                saved symbol-ISIN mappings. If not provided, an empty dataset
                is initialized.
        """
        if data_file is None:
            self.data = SymbolISINMap(sym2isin={}, isin2hist={})
        else:
            self.data = self.from_json(data_file)

    def update(self, symbol: str, isin: str, dt: date):
        """
        Updates the tracker with a symbol-ISIN mapping for a given date.

        If the ISIN already exists:
            - Extends the date range if the symbol matches the latest entry.
            - Adds a new history entry if the symbol is new for the ISIN.
            - Raises an error if inconsistencies are detected.

        If the ISIN does not exist:
            - Creates a new history entry and mapping.

        Args:
            symbol (str): The trading symbol.
            isin (str): The ISIN associated with the symbol.
            dt (date): The date of the update.

        Raises:
            ValueError: If conflicting mappings or unexpected history states
                are encountered.
        """
        if isin in self.data["isin2hist"]:
            if symbol in self.data["sym2isin"]:
                if self.data["sym2isin"][symbol] == isin:
                    last = self.data["isin2hist"][isin][-1]

                    if last["symbol"] == symbol:
                        last["to_date"] = dt
                    else:
                        raise ValueError(
                            f"Expected last entry for {isin} to be {symbol}: got {last['symbol']}"
                        )
                else:
                    raise ValueError(
                        f"Expected {self.data['sym2isin'][symbol]} for {symbol}: got {isin}"
                    )

            else:
                self.data["sym2isin"][symbol] = isin
                self.data["isin2hist"][isin].append(
                    SymbolHistory(
                        symbol=symbol,
                        from_date=dt,
                        to_date=dt,
                        action=None,
                    )
                )
        else:
            self.data["isin2hist"][isin] = [
                SymbolHistory(symbol=symbol, from_date=dt, to_date=dt, action=None)
            ]
            self.data["sym2isin"][symbol] = isin

    def get_last_symbol(self, key: str, by: Literal["isin", "symbol"]) -> Optional[str]:
        """
        Retrieves the most recent symbol associated with the given key.

        Args:
            key (str): The ISIN or symbol to query.
            by (Literal["isin", "symbol"]): Specifies whether the key is an ISIN
                or a symbol.

        Returns:
            Optional[str]: The latest symbol if found, otherwise None.
        """
        if by == "isin":
            result = self.data["isin2hist"].get(key)
            return None if not result else result[-1]["symbol"]

        isin = self.data["sym2isin"].get(key)

        if isin is None:
            return None

        result = self.data["isin2hist"].get(isin)

        return None if not result else result[-1]["symbol"]

    def get_history(
        self,
        key: str,
        by: Literal["isin", "symbol"],
    ) -> Optional[List[SymbolHistory]]:
        """
        Retrieves the full symbol history for a given ISIN or symbol.

        Args:
            key (str): The ISIN or symbol to query.
            by (Literal["isin", "symbol"]): Specifies whether the key is an ISIN
                or a symbol.

        Returns:
            Optional[List[SymbolHistory]]: A list of historical records if found,
                otherwise None.
        """
        if by == "isin":
            return self.data["isin2hist"].get(key)

        isin = self.data["sym2isin"].get(key)

        if isin is None:
            return None
        return self.data["isin2hist"].get(isin)

    def to_json(self) -> str:
        """
        Serializes the current symbol-ISIN mapping data to a JSON string.

        Dates are converted to ISO 8601 string format.

        Returns:
            str: A JSON-formatted string representing the internal state.
        """
        result = dict(
            sym2isin=self.data["sym2isin"],
            isin2hist={
                isin: [
                    {
                        **entry,
                        "from_date": entry["from_date"].isoformat(),
                        "to_date": entry["to_date"].isoformat(),
                    }
                    for entry in hist
                ]
                for isin, hist in self.data["isin2hist"].items()
            },
        )

        return json.dumps(result, indent=2)

    @staticmethod
    def from_json(file: Path) -> SymbolISINMap:
        """
        Loads symbol-ISIN mapping data from a JSON file.

        Converts date strings back into `date` objects.

        Args:
            file (Path): Path to the JSON file containing serialized data.

        Returns:
            SymbolISINMap: The reconstructed mapping data.
        """
        result = json.loads(file.read_text())

        return cast(
            SymbolISINMap,
            dict(
                sym2isin=result["sym2isin"],
                isin2hist={
                    isin: [
                        {
                            **entry,
                            "from_date": date.fromisoformat(entry["from_date"]),
                            "to_date": date.fromisoformat(entry["to_date"]),
                        }
                        for entry in hist
                    ]
                    for isin, hist in result["isin2hist"].items()
                },
            ),
        )
