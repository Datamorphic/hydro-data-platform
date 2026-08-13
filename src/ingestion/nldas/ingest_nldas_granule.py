from nldas_client import NLDASClient

if __name__ == '__main__':

    # TODO: Handle user input about grnaule
    # Wo do we get all necessary granule metadata into this program
    # as well any spatial subetting information (if applicable).

    client = NLDASClient()
    client.authenticate()

    # If full granule
    client.download_granule()

    # If subset granule
    client.download_subset_granule()

