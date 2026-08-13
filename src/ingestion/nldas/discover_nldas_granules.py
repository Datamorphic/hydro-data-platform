from ingestion.nldas.nldas_client import NLDASClient

def write_granules_to_file(granule_metadata: dict): # maybe make a granule class object so we control the handoff instead of arbitrary dictionary?
    '''
    Function that writes NLDAS granules meta-data
    to a json file
    '''
    ...

if __name__ == '__main__':

    # TODO: Handle user input. Needs to know daterange for NLDAS retrieval and other relivant info
    client = NLDASClient()
    client.authenticate()
    granules = client.search_granules()
    write_granules_to_file(granules)