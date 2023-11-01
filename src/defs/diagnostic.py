from pandas import read_csv
from pathlib import Path

'''
This script checks data integrity of all csv files in eod2_data/daily and eod2_data/delivery folders.

It checks for:
- Empty files
- Corrupt or incorrectly formatted files
- Duplicate entries in files
- Mismatch in column dataTypes. Strings or NAN in place of Int or Float

By default only a maximum of 5 errors are printed. Edit the ERROR_THRESHOLD variable to print more error. Once error is corrected must rerun to verify.

EOD2 takes extreme care to ensure data integrity but it is possible due to bugs or accidental user inputs.

Run this script periodically and report any errors by raising an issue:
https://github.com/BennyThadikaran/eod2/issues

Your reporting helps make EOD2 rock solid and stable.
'''

ERROR_THRESHOLD = 5

DIR = Path(__file__).parents[1]

duplicatesList = []
typeMismatchList = []
indexMismatchList = []
exceptionsList = []
dlvColLenMismatch = []
dailyColLenMismatch = []


def reset():
    duplicatesList.clear()
    typeMismatchList.clear()
    indexMismatchList.clear()
    exceptionsList.clear()
    dlvColLenMismatch.clear()
    dailyColLenMismatch.clear()


def getErrorCount():
    return max(len(duplicatesList),
               len(typeMismatchList),
               len(indexMismatchList),
               len(exceptionsList),
               len(dlvColLenMismatch))


def printResult(folder):
    print('Folder: ', folder.name.upper())

    if getErrorCount() == 0:
        print(f'No errors\n')
        return

    if len(duplicatesList):
        print('\nDuplicate entries')
        print('\n'.join(duplicatesList))

    if len(typeMismatchList):
        print('\nDatatype mismatch')
        print('\n'.join(typeMismatchList))

    if len(indexMismatchList):
        print('\nPandas Index mismatch')
        print('\n'.join(indexMismatchList))

    if len(exceptionsList):
        print('\nFile or Pandas exceptions')
        print('\n'.join(exceptionsList))

    if folder.name == 'daily' and len(dailyColLenMismatch):
        print('\nColumn mismatch')
        print('\n'.join(dailyColLenMismatch))

    if folder.name == 'delivery' and len(dlvColLenMismatch):
        print('\nColumn mismatch')
        print('\n'.join(dlvColLenMismatch))


def diagnose(file: Path, folderName: str, expectedColumnLen: int):
    try:
        df = read_csv(file, index_col='Date',
                      parse_dates=True)
    except Exception as e:
        # Catch pandas or file parsing errors
        exceptionsList.append(f'{child.name.upper()}: {e!r}')
        return

    # File is empty or only has column headings
    if df.shape[0] < 1:
        print(f'{folderName}/{file.name} is empty.')
        return

    # Catch Type errors in Datetime index
    if df.index.dtype != 'datetime64[ns]':
        txt = indexMismatchText.format(
            child.name.upper().ljust(15),
            df.index.dtype)

        indexMismatchList.append(txt)

    columns = df.columns
    colLength = len(columns)

    # Catch column length errors
    if colLength != expectedColumnLen:
        txt = columnMismatchText.format(
            child.name.upper().ljust(15),
            expectedColumnLen,
            colLength
        )

        if folderName == 'daily':
            dailyColLenMismatch.append(txt)
        else:
            dlvColLenMismatch.append(txt)

    # Catch column dataType mismatch
    for col in df.columns:
        if not df[col].dtype in ('float64', 'int64'):
            txt = dtypeMismatchText.format(
                child.name.upper().ljust(15),
                col,
                df[col].dtype)

            typeMismatchList.append(txt)

    # Catch duplicate entries in file
    if df.index.has_duplicates:
        duplicatesList.append(child.name.upper())


daily = DIR / 'eod2_data' / 'daily'

dtypeMismatchText = '{}: Column type Mismatch in {}. Expected float64 or int64. Got {}'
columnMismatchText = '{}: Column Length Mismatch. Expect {} got {}'
indexMismatchText = '{}: Pandas Index type Mismatch. Expect datetime64[ns] got {}'

for child in daily.iterdir():

    diagnose(child, 'daily', 5)

    if max(len(duplicatesList),
           len(typeMismatchList),
           len(indexMismatchList),
           len(exceptionsList),
           len(dailyColLenMismatch)) >= 5:
        break

printResult(daily)
