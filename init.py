import defs

defs.dates.getLastUpdated()

with defs.NSE() as nse:
    while True:
        defs.dates.getNextDate()

        if defs.checkForHolidays(nse):
            continue

        # Validate NSE actions file
        defs.validateNseActionsFile(nse)

        # Download all files and validate for errors
        print('Downloading Files')

        # NSE bhav copy
        bhav_file = defs.downloadNseBhav(nse)

        # NSE delivery
        delivery_file = defs.downloadNseDelivery(nse)

        # Index file
        index_file = defs.downloadIndexFile(nse)

        try:
            print('Starting Data Sync')

            defs.updateNseEOD(bhav_file)

            print('EOD sync complete')

            defs.updateDelivery(delivery_file)

            print('Delivery sync complete')

            # INDEX sync
            defs.updateIndexEOD(index_file)

            print('Index sync complete.')
        except Exception as e:
            # rollback
            print(f"Error during data sync. {e!r}")
            defs.rollback(defs.daily_folder)
            defs.rollback(defs.delivery_folder)
            exit()

        # No errors continue

        # Adjust Splits and bonus
        print('Makings adjustments for splits and bonus')

        try:
            defs.adjustNseStocks()
        except Exception as e:
            print(
                f"Error while making adjustments. {e!r}\nAll adjustments have been discarded.")
            defs.rollback(defs.daily_folder)
            defs.rollback(defs.delivery_folder)
            exit()

        print('Cleaning up files')

        defs.cleanup((bhav_file, delivery_file, index_file))

        defs.dates.setLastUpdated()

        print(f'{defs.dates.dt:%d %b %Y}: Done\n{"-" * 52}')
