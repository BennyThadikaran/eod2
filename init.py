import defs

defs.dt = defs.getLastUpdated()

while True:
    defs.dt = defs.getNextDate(defs.dt)
    defs.pandas_dt = defs.dt.strftime('%Y-%m-%d')

    if defs.checkForHolidays(defs.dt):
        continue

    # Validate NSE actions file
    defs.validateNseActionsFile()

    # Download all files and validate for errors
    print('Downloading Files')

    # NSE bhav copy
    bhav_file = defs.downloadNseBhav()

    # NSE delivery
    delivery_file = defs.downloadNseDelivery()

    # Index file
    index_file = defs.downloadIndexFile()

    # NSE sync
    print('Starting Data Sync')

    defs.updateNseEOD(bhav_file)

    print('EOD sync complete')

    defs.updateDelivery(delivery_file)

    print('Delivery sync complete')

    # INDEX sync
    defs.updateIndexEOD(index_file)

    print('Index sync complete.')

    # Adjust Splits and bonus
    print('Makings adjustments for splits and bonus')

    defs.adjustNseStocks()

    print('Cleaning up files')

    defs.cleanup((bhav_file, delivery_file, index_file))

    defs.setLastUpdated(defs.dt)

    print(f'{defs.dt:%d %b %Y}: Done\n{"-" * 52}')

