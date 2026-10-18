"""OrgMind Ingestion Service Package."""

from orgmind.ingest.connectors.base import BaseConnector, ConnectorItem, NormalisedItem, RawPayload
from orgmind.ingest.connectors.file_upload import FileUploadConnector
from orgmind.ingest.connectors.sample_data import SampleDataConnector
from orgmind.ingest.connectors.watched_folder import WatchedFolderConnector
from orgmind.ingest.pipeline import IngestionPipeline, run_ingestion_job

__all__ = [
    "BaseConnector",
    "ConnectorItem",
    "RawPayload",
    "NormalisedItem",
    "FileUploadConnector",
    "WatchedFolderConnector",
    "SampleDataConnector",
    "IngestionPipeline",
    "run_ingestion_job",
]
