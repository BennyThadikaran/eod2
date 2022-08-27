#!/bin/python3

import defs

lastUpdatedFile = '/lastupdate.txt'
defs.dt = defs.getLastUpdated(lastUpdatedFile)

while True:
    defs.dt = defs.getNextDate(defs.dt)
    defs.pandas_dt = defs.dt.strftime('%Y-%m-%d')
    if defs.checkForHolidays(defs.dt):
        continue

    # Validate NSE actions file
    defs.validateNseActionsFile()

    # Download all files and validate for errors
    print('Downloading Files')

    # NSE
    bhavFile = defs.downloadNseBhav()

    # NSE delivery
    dq_df = defs.downloadNseDelivery()

    # Index file
    index_df = defs.downloadIndexFile()

    # Begin sync
    # NSE sync
    print('Starting Data Sync')

    defs.updateNseEOD(bhavFile)

    print('EOD sync complete')

    defs.updateDelivery(dq_df)

    print('Delivery sync complete')

    # INDEX sync
    defs.updateIndexEOD(index_df)

    print('Index sync complete.')

    # Adjust Splits and bonus
    print('Makings adjustments for splits and bonus')

    defs.adjustNseStocks()

    print('Cleaning up files')

    defs.cleanup([bhavFile])

    defs.setLastUpdated(defs.dt, lastUpdatedFile)

    print(f'{defs.dt:%d %b %Y}: Done\n{"-" * 52}')

