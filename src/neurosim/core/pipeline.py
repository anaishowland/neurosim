"""Database access helpers for pipeline tasks.

This module manages PostgreSQL connections and retrieves tasks linked to a
given pipeline using environment-configured credentials or a connection string.
"""


import os
import logging
from contextlib import contextmanager
from typing import Dict, List, Optional
from pydantic import BaseModel

import psycopg as pg
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()  # Load environment variables from a .env file if present

class ConnectionConfig(BaseModel):
    """Optional connection parameters used to build a PostgreSQL conninfo DSN."""

    db_name: Optional[str]
    db_user: Optional[str]
    db_password: Optional[str]
    db_host: Optional[str]
    db_port: Optional[str]

class PipelineDBError(Exception):
    """Custom exception for PipelineDB errors."""



class PipelineDB:
    """
    PipelineDB is a class that manages the connection to a PostgreSQL database
    and provides methods to interact with the database, specifically for 
    retrieving tasks associated with a given pipeline.

    Attributes:
        connection_string (str): The connection string for the PostgreSQL database.
        db_name (str): The name of the database.
        db_user (str): The username for the database.
        db_password (str): The password for the database.
        db_host (str): The host address of the database.
        db_port (str): The port number for the database connection.
        conn: The connection object for the database.

    Methods:
        __enter__(): Opens the database connection and returns the instance.
        __exit__(exc_type, exc_val, exc_tb): Closes the database connection.
        open(): Establishes a connection to the database.
        close(): Closes the database connection if it is open.
        get_pipeline_tasks(pipeline_id: str) -> List[Dict[str, str]]:
            Retrieves tasks associated with a given pipeline ID from the database.
    """
    conn: Optional[pg.Connection]

    def __init__(self,
                 connection_string: Optional[str] = None,
                 db_config: Optional[ConnectionConfig] = None
                ):
        """
        Initialize PipelineDB with database connection parameters.

        Args:
            connection_string: PostgreSQL connection string
            db_name: Database name
            db_user: Database username
            db_password: Database password
            db_host: Database host
            db_port: Database port

        Note:
            If parameters are not provided, they will be loaded from environment variables.
        """
        self.connection_string = connection_string or os.getenv(
            "PRISMA_CONNECTION_STRING")

        cfg = db_config or ConnectionConfig(
            db_name=os.getenv("PRISMA_DB_NAME"),
            db_user=os.getenv("PRISMA_DB_USER"),
            db_password=os.getenv("PRISMA_DB_PASSWORD"),
            db_host=os.getenv("PRISMA_DB_HOST"),
            db_port=os.getenv("PRISMA_DB_PORT"),
        )

        self.db_name = cfg.db_name
        self.db_user = cfg.db_user
        self.db_password = cfg.db_password
        self.db_host = cfg.db_host
        self.db_port = cfg.db_port
        self.conn = None

        # Log connection parameters (without sensitive data)
        self._log_connection_info()

        # Validate required parameters
        self._validate_connection_params()

    def _build_conninfo(self) -> str:
        """Build a libpq conninfo string from individual parameters."""
        return (
            f"dbname={self.db_name} "
            f"user={self.db_user} "
            f"password={self.db_password} "
            f"host={self.db_host} "
            f"port={self.db_port}"
        )

    def _log_connection_info(self) -> None:
        """Log connection information for debugging (without sensitive data)."""
        if self.connection_string:
            logger.info("Using connection string for database connection")
        else:
            db_name_value = self.db_name or 'NOT SET'
            user_value = self.db_user or 'NOT SET'
            logger.info(
                "Database connection parameters: host=%s, port=%s, db_name=%s, user=%s",
                self.db_host,
                self.db_port,
                db_name_value,
                user_value
            )
            if not self.db_name:
                logger.warning(
                    "Database name is not set. \
                    Please set PRISMA_DB_NAME environment variable or pass db_name parameter.\
                    ")
            if not self.db_user:
                logger.warning(
                    "Database user is not set. \
                    Please set PRISMA_DB_USER environment variable or pass db_user parameter.")
            if not self.db_password:
                logger.warning(
                    "Database password is not set. \
                    Please set PRISMA_DB_PASSWORD environment variable or pass \
                    db_password parameter.")
            if not self.db_host:
                logger.warning(
                    "Database host is not set. \
                    Please set PRISMA_DB_HOST environment variable or pass db_host parameter.")

    def _validate_connection_params(self) -> None:
        """Validate that required connection parameters are provided."""
        if self.connection_string:
            return  # Connection string is provided, no need to validate individual params

        # Check which individual parameters are missing
        missing_params = []
        if not self.db_name:
            missing_params.append("PRISMA_DB_NAME")
        if not self.db_user:
            missing_params.append("PRISMA_DB_USER")
        if not self.db_password:
            missing_params.append("PRISMA_DB_PASSWORD")
        if not self.db_host:
            missing_params.append("PRISMA_DB_HOST")

        if missing_params:
            raise PipelineDBError(
                f"Missing required database parameters: {', '.join(missing_params)}. "
                f"Please set these environment variables or \
                pass them as parameters to the constructor."
            )

    def __enter__(self) -> "PipelineDB":
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Close the database connection."""
        if self.conn:
            try:
                if hasattr(self.conn, "close"):
                    self.conn.close()
                    logger.info("Database connection closed")
                else:
                    logger.warning("Connection object has no close() method")
            except pg.Error as e:
                logger.error("Error closing database connection: %s", e)
            finally:
                self.conn = None

    def open(self) -> None:
        """
        Establishes a connection to the PostgreSQL database using the provided
        connection parameters. If the connection is successful, a connection
        object is assigned to the `self.conn` attribute. If the connection fails,
        an error is logged and `self.conn` is set to None.

        Raises:
            PipelineDBError: If there is an error connecting to the database.
        """
        try:
            conninfo = self.connection_string or self._build_conninfo()
            self.conn = pg.connect(conninfo=conninfo)
            logger.info("Database connection established successfully")
        except pg.OperationalError as e:
            logger.error("Failed to connect to database: %s", e)
            raise PipelineDBError(f"Database connection failed: {e}") from e
        except pg.Error as e:
            logger.error("Unexpected error during database connection: %s", e)
            raise PipelineDBError(f"Unexpected error: {e}") from e

    def _validate_pipeline_id(self, pipeline_id: str) -> None:
        """Validate pipeline_id parameter."""
        if not pipeline_id or not isinstance(pipeline_id, str):
            raise ValueError("pipeline_id must be a non-empty string")

    @contextmanager
    def _get_cursor(self):
        """Context manager for database cursor."""
        if not self.conn:
            raise PipelineDBError("No database connection available")
        try:
            with self.conn.cursor() as cursor:
                yield cursor
        except AttributeError as e:
            logger.error("Attribute error: %s", e)
            raise PipelineDBError("The connection object does not have a 'cursor' method") from e
        except pg.Error as e:
            logger.error("Database cursor error: %s", e)
            raise PipelineDBError(f"Database operation failed: {e}") from e

    def get_pipeline_tasks(self, pipeline_id: str) -> List[Dict[str, str]]:
        """
        Retrieves a list of tasks associated with a given pipeline ID.

        This method executes a SQL query to fetch tasks from the database
        that are linked to the specified pipeline. Each task is represented
        as a dictionary containing the task ID and task name.

        Args:
            pipeline_id (str): The unique identifier of the pipeline for which
                               tasks are to be retrieved.

        Returns:
            List[Dict[str, str]]: A list of dictionaries, each containing the
                                  'taskId' and 'task' name. If no tasks are found,
                                  an empty list is returned.

        Raises:
            ValueError: If pipeline_id is invalid
            PipelineDBError: If database operation fails
        """
        self._validate_pipeline_id(pipeline_id)

        query: str = '''
            SELECT
                vt."id" AS taskId,
                t."name" AS task
            FROM
                "Pipeline" p
            JOIN
                "_PipelineToVendorTask" pv ON pv."A" = p."id"
            JOIN
                "VendorTask" vt ON vt."id" = pv."B"
            JOIN
                "Task" t ON t."id" = vt."taskId"
            WHERE
                p."id" = %s;
        '''

        try:
            with self._get_cursor() as cur:
                cur.execute(query, (pipeline_id,))
                rows = cur.fetchall()
                tasks = [
                    {"taskId": str(row[0]), "task": row[1]}
                    for row in rows
                ]
                logger.info("Retrieved %d tasks for pipeline %s",
                            len(tasks), pipeline_id)
                return tasks
        except pg.Error as e:
            logger.error(
                "Failed to retrieve tasks for pipeline %s: %s", pipeline_id, e)
            raise PipelineDBError(
                f"Failed to retrieve pipeline tasks: {e}") from e


if __name__ == "__main__":
    PIPELINE: str = "1"  # Set this to the desired Pipeline id

    try:
        with PipelineDB() as db:
            result = db.get_pipeline_tasks(PIPELINE)
            print(f"Query result: {len(result)} tasks found")
            for task in result:
                print(f"Task ID: {task['taskId']}, Task: {task['task']}")
    except PipelineDBError as e:
        print(f"Database error: {e}")
    except (ValueError, pg.Error) as e:
        print(f"Unexpected error: {e}")
