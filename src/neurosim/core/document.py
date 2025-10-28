"""
Class to upload documents to Google Firestore.
"""


import os
import logging
from typing import Union
from google.cloud import firestore

from google.api_core import exceptions


class GFSUploader:
    """Class to upload documents to Google Firestore."""

    def __init__(self, job_id: str):
        self.job_id = job_id
        try:
            self.document_db = firestore.Client(
                project=os.getenv("GCP_PROJECT_ID"),
                database=os.getenv("FIRESTORE_DATABASE"))
            self.document = self.__initialize_document__()
        except (exceptions.GoogleAPIError, exceptions.ClientError) as e:
            logging.error("Error initializing Monitor - %s", e)
            raise

    def __initialize_document__(self) -> firestore.DocumentReference:
        """
        Initialize the document
        """
        doc_ref = self.document_db.collection(
            os.getenv("FIRESTORE_COLLECTION", "")).document(self.job_id)
        return doc_ref

    def update(self, data: dict[str, Union[str, float, int]], merge: bool = True) -> None:
        """
        Upload the payload to Firestore
        """
        try:
            self.document.set(data, merge)
        except (exceptions.GoogleAPIError, exceptions.ClientError) as e:
            logging.error("Error uploading payload - %s", e)
            raise
