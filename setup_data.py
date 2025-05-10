from pathlib import Path
from shutil import copyfileobj
from zipfile import ZipFile

try:
    import httpx
except ModuleNotFoundError:
    exit(f"Please run `pip install -U nse[server]`")

# ################################
# This script is written for non git users,
# who may download this repository as a zip file.
# The zip file does not install the submodule eod2_data.
#
# This script will download the eod2_data as a zip and
# extract the contents into eod2_data folder.
# ################################

DIR = Path(__file__).parent
url = "https://github.com/BennyThadikaran/eod2_data/archive/main.zip"
ZIP_FILE = DIR / "eod2_data.zip"
FOLDER = DIR / "src" / "eod2_data"
DAILY_FOLDER = FOLDER / "daily"

if not FOLDER.exists():
    FOLDER.mkdir()
elif any(FOLDER.iterdir()):
    # check if the folder has any files in it
    print("eod2_data folder has data. Renaming folder to eod2_data_backup.")

    # Rename the folder to protect files from being overwritten.
    FOLDER.rename("eod2_data_backup")

with httpx.Client(
    timeout=30, transport=httpx.HTTPTransport(http2=True, retries=2)
) as session:
    with session.stream("GET", url, follow_redirects=True) as r:
        with ZIP_FILE.open("wb") as f:
            print(f"Downloading eod2_data from {url}")
            # 15 mb chunk size
            for chunk in r.iter_bytes(chunk_size=15 * 1024 * 1024):
                f.write(chunk)

if not ZIP_FILE.is_file():
    exit("download failed")

print("Download success.")
# create the eod2_data and daily folder if not exists
if not FOLDER.exists():
    FOLDER.mkdir()

if not DAILY_FOLDER.exists():
    DAILY_FOLDER.mkdir()

print("Extracting Zipfile to eod2_data")

with ZipFile(ZIP_FILE) as zip:
    for filePath in zip.namelist():
        # zip file comes in eod2_data-main,
        # we dont need the folder so remove it from filepath
        outPath = FOLDER / filePath.replace("eod2_data-main/", "")

        if outPath.is_dir():
            continue

        with zip.open(filePath) as src:
            with outPath.open("wb") as dst:
                # copy file from src to dst without extracting them to disk
                copyfileobj(src, dst)

ZIP_FILE.unlink()
print("Done")
