from nomz.ingestion.sources.socrata_client import SocrataResource

EATERIES = SocrataResource(
    dataset_id="8792-ebcp",
    name="Directory of Eateries",
    fields=None,
)

DINING_OUT = SocrataResource(
    dataset_id="fpeh-f7ci",
    name="Dining Out NYC Locations",
    fields=None,
)

INSPECTIONS = SocrataResource(
    dataset_id="43nn-pn8j",
    name="DOHMH Restaurant Inspection Results",
    fields=None,
)


ALL_SOURCE_DEFS = [EATERIES, DINING_OUT, INSPECTIONS]
