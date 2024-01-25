import pandas as pd
from pathlib import Path

"""
This script checks data integrity of all csv files in eod2_data/daily.

It checks for:
- Empty files
- Corrupt or incorrectly formatted files
- Duplicate entries in files
- Incorrect column dataTypes.
- NAN values in OHLCV rows

By default only a maximum of 5 errors are printed. Edit the ERROR_THRESHOLD variable to print more error. Once error is corrected must rerun to verify.

EOD2 takes extreme care to ensure data integrity but it is possible due to bugs or accidental user inputs.

Run this script periodically and report any errors by raising an issue:
https://github.com/BennyThadikaran/eod2/issues

Your reporting helps make EOD2 rock solid and stable.
"""

ERROR_THRESHOLD = 5

DIR = Path(__file__).parents[1]

duplicatesList = []
typeMismatchList = []
indexMismatchList = []
exceptionsList = []
colMismatchList = []
hasNansList = []


def getErrorCount():
    return max(
        len(duplicatesList),
        len(typeMismatchList),
        len(indexMismatchList),
        len(exceptionsList),
        len(colMismatchList),
        len(hasNansList),
    )


def printResult():
    if getErrorCount() == 0:
        print("No errors\n")
        return

    if len(duplicatesList):
        print("\nDuplicate entries")
        print("\n".join(duplicatesList))

    if len(typeMismatchList):
        print("\nDatatype mismatch")
        print("\n".join(typeMismatchList))

    if len(indexMismatchList):
        print("\nPandas Index mismatch")
        print("\n".join(indexMismatchList))

    if len(exceptionsList):
        print("\nFile or Pandas exceptions")
        print("\n".join(exceptionsList))

    if len(colMismatchList):
        print("\nColumn mismatch")
        print("\n".join(colMismatchList))

    if len(hasNansList):
        print("\nColumn with NaN values")
        print("\n".join(hasNansList))


daily = DIR / "eod2_data" / "daily"

dtypeMismatchText = (
    "{}: Column type Mismatch in {}. Expected float64 or int64. Got {}"
)
columnMismatchText = "{}: Column Length Mismatch. Expect {} got {}"
indexMismatchText = (
    "{}: Pandas Index type Mismatch. Expect datetime64[ns] got {}"
)
hasNansText = "{}: Column {} has NAN values"

for child in daily.iterdir():
    try:
        df = pd.read_csv(child, index_col="Date", parse_dates=True)
    except Exception as e:
        # Catch pandas or file parsing errors
        exceptionsList.append(f"{child.name.upper()}: {e!r}")
        continue

    # File is empty or only has column headings
    if df.shape[0] < 1:
        print(f"daily/{child.name} is empty.")
        continue

    # Catch Type errors in Datetime index
    if df.index.dtype != "datetime64[ns]":
        txt = indexMismatchText.format(
            child.name.upper().ljust(15), df.index.dtype
        )

        indexMismatchList.append(txt)

    columns = df.columns
    colLength = len(columns)

    # Catch column length errors
    if colLength != 8:
        txt = columnMismatchText.format(
            child.name.upper().ljust(15), 5, colLength
        )

        colMismatchList.append(txt)

    # Catch column dataType mismatch
    for col in df.columns:
        if df[col].dtype not in ("float64", "int64"):
            txt = dtypeMismatchText.format(
                child.name.upper().ljust(15), col, df[col].dtype
            )

            typeMismatchList.append(txt)

    for col in ("Open", "High", "Low", "Close", "Volume"):
        if df[col].hasnans:
            hasNansList.append(
                hasNansText.format(child.name.upper().ljust(15), col)
            )

    # Catch duplicate entries in file
    if df.index.has_duplicates:
        duplicatesList.append(child.name.upper())

    if getErrorCount() >= ERROR_THRESHOLD:
        break

printResult()
