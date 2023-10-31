from sys import platform

try:
    from nse import NSE
except ModuleNotFoundError:
    # Inform user to install nse.
    pip = 'pip' if 'win' in platform else 'pip3'

    exit(f"EOD2 requires 'nse' package. Run '{pip} install -U nse'")

import json
from defs import defs
from argparse import ArgumentParser
# from sys import argv

parser = ArgumentParser(prog='init.py')

group = parser.add_mutually_exclusive_group()

group.add_argument('-v',
                   '--version',
                   action='store_true',
                   help='Print the current version.')

group.add_argument('-c',
                   '--config',
                   action='store_true',
                   help='Print the current config.')

args = parser.parse_args()

if args.version:
    exit(f'EOD2 init.py: version {defs.config.VERSION}')

if args.config:
    exit(str(defs.config))

nse = NSE(defs.DIR)

if defs.config.AMIBROKER and not defs.isAmiBrokerFolderUpdated():
    defs.updateAmiBrokerRecords(nse)

while True:
    defs.dates.getNextDate()

    if defs.checkForHolidays(nse):
        continue

    # Validate NSE actions file
    defs.validateNseActionsFile(nse)

    # Download all files and validate for errors
    print('Downloading Files')

    try:
        # NSE bhav copy
        BHAV_FILE = nse.equityBhavcopy(defs.dates.dt)

        # NSE delivery
        DELIVERY_FILE = nse.deliveryBhavcopy(defs.dates.dt)

        # Index file
        INDEX_FILE = nse.indicesBhavcopy(defs.dates.dt)
    except (RuntimeError, Exception) as e:
        exit(repr(e))

    try:
        print('Starting Data Sync')

        defs.updateNseEOD(BHAV_FILE)

        print('EOD sync complete')

        defs.updateDelivery(DELIVERY_FILE)

        print('Delivery sync complete')

        # INDEX sync
        defs.updateIndexEOD(INDEX_FILE)

        print('Index sync complete.')
    except Exception as e:
        # rollback
        print(f"Error during data sync. {e!r}")
        defs.rollback(defs.DAILY_FOLDER)
        defs.rollback(defs.DELIVERY_FOLDER)

        defs.dates.dt = defs.dates.lastUpdate
        defs.meta['lastUpdate'] = defs.dates.dt.isoformat()
        defs.META_FILE.write_text(json.dumps(defs.meta, indent=2))
        exit()

    # No errors continue

    # Adjust Splits and bonus
    print('Makings adjustments for splits and bonus')

    try:
        defs.adjustNseStocks()
    except Exception as e:
        print(
            f"Error while making adjustments. {e!r}\nAll adjustments have been discarded.")

        defs.rollback(defs.DAILY_FOLDER)
        defs.rollback(defs.DELIVERY_FOLDER)

        defs.dates.dt = defs.dates.lastUpdate
        defs.meta['last_update'] = defs.dates.dt.isoformat()
        defs.META_FILE.write_text(json.dumps(defs.meta, indent=2))
        exit()

    print('Cleaning up files')

    defs.cleanup((BHAV_FILE, DELIVERY_FILE, INDEX_FILE))

    defs.dates.lastUpdate = defs.dates.dt
    defs.meta['lastUpdate'] = defs.dates.dt.isoformat()
    defs.META_FILE.write_text(json.dumps(defs.meta, indent=2))

    print(f'{defs.dates.dt:%d %b %Y}: Done\n{"-" * 52}')
