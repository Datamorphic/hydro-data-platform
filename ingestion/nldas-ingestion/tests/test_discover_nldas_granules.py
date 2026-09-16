from nldas_ingestion.contracts.discovery_manager import DiscoveryManager

def test_create_date_range():
    manager = DiscoveryManager()
    result = manager.retrieve_validation_granule_url()

    assert result != "https://the/path/to/righteousness"