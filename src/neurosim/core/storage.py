"""Google Cloud Storage upload utilities.

This module provides a class-based API focused on uploading JSON and PNG data
to Google Cloud Storage (GCS). JSON uploads support optional Zstandard (zstd)
compression, using content type ``application/zstd`` with content encoding
``zstd`` when compression is enabled.

Quick examples:

    from neurosim.core.storage import GCSUploader

    # set env: export GCS_BUCKET_NAME=my-bucket
    uploader = GCSUploader()

    # Upload JSON (optionally zstd-compressed)
    uri = uploader.upload_json("path/to/blob.json", {"k": "v"}, compress_zstd=True)

    # Upload PNG bytes
    uri = uploader.upload_png(png_bytes, "path/to/image.png")

Optional dependencies:
- google-cloud-storage: required. Install via ``pip install neurosim[gcs]``
- zstandard: optional, only for ``compress_zstd`` in JSON uploads. 

Install via ``pip install neurosim[zstd]``
"""

from __future__ import annotations

import json
import logging
import argparse
from pathlib import Path
from typing import Any, Mapping, Optional
import os

# Optional dependency: google-cloud-storage
try:
    from google.cloud import storage  # type: ignore
    from google.cloud.storage import Client
except ImportError:  # pragma: no cover - optional dependency guard
    storage = None  # type: ignore[assignment]

# Optional dependency: zstandard (for JSON compression)
try:
    import zstandard as zstd  # type: ignore
except ImportError:  # pragma: no cover - optional dependency guard
    zstd = None  # type: ignore[assignment]


logger = logging.getLogger(__name__)


def _ensure_gcs_client(client: Optional[Any]) -> Client:
    """Return a ``google.cloud.storage.Client`` instance, importing on-demand.

    Raises a RuntimeError if the optional dependency is missing.
    """
    if client is not None:
        return client
    if storage is None:
        raise RuntimeError(
            "google-cloud-storage is required. Install with `pip install neurosim[gcs]`."
        )
    return storage.Client()


class GCSUploader:
    """Uploader for JSON and PNG content to GCS.

    Create once and reuse to share the same underlying GCS client across uploads.
    """

    def __init__(self, client: Optional[Any] = None, bucket_name: Optional[str] = None) -> None:
        """Initialize uploader with a GCS client and optional bucket name."""
        self._client = _ensure_gcs_client(client)
        self._bucket_name = bucket_name or os.environ.get("GCS_BUCKET_NAME")

    @property
    def bucket_name(self) -> str:
        """Return the configured GCS bucket name or raise if unset."""
        bucket = self._bucket_name
        if not bucket:
            raise RuntimeError(
                "GCS bucket not configured. Set the GCS_BUCKET_NAME environment variable or "
                "initialize GCSUploader(bucket_name=...)"
            )
        return bucket

    def _upload_bytes(
        self,
        *,
        data: bytes,
        blob_path: str,
        content_type: str,
        content_encoding: Optional[str] = None,
        make_public: bool = False,
        action_desc: str,
    ) -> str:
        """Upload bytes to GCS with logging.

        Args:
            data: Raw bytes to upload.
            bucket_name: Name of the GCS bucket.
            blob_path: Object path within the bucket.
            content_type: MIME type for the object.
            content_encoding: Optional content-encoding (e.g. ``zstd``).
            make_public: If True, make the object publicly readable.
            action_desc: Short human-readable description for logs.

        Returns:
            The ``gs://`` URI of the uploaded object.
        """
        bucket_name = self.bucket_name
        print(f"data: {len(data)} bytes")
        logger.info(
            "Uploading to GCS: %s (bucket=%s, blob=%s, content_type=%s, content_encoding=%s)",
            action_desc,
            bucket_name,
            blob_path,
            content_type,
            content_encoding or "<none>",
        )

        bucket = self._client.bucket(bucket_name)
        blob = bucket.blob(blob_path)

        if content_encoding:
            blob.content_encoding = content_encoding

        blob.upload_from_string(data, content_type=content_type)

        if make_public:
            blob.make_public()

        uri = f"gs://{bucket_name}/{blob_path}"
        logger.info("Upload successful: %s -> %s", blob_path, uri)
        return uri

    def upload_png(self, data: bytes, blob_path: str, *, make_public: bool = False) -> str:
        """Upload PNG bytes to GCS.

        Returns the ``gs://`` URI of the uploaded object.
        """
        return self._upload_bytes(
            data=data,
            blob_path=blob_path,
            content_type="image/png",
            make_public=make_public,
            action_desc="PNG upload",
        )

    def upload_json(
        self,
        blob_path: str,
        data: Mapping[str, Any] | Any,
        *,
        make_public: bool = False,
        compress_zstd: bool = True,
        zstd_level: int = 3,
    ) -> str:
        """Upload data as JSON to GCS.

        - If ``compress_zstd`` is False (default):
          content type is ``application/json; charset=utf-8``.
        - If ``compress_zstd`` is True: payload is zstd-compressed, content type
          is ``application/zstd`` and content encoding is ``zstd``.
        """
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        original_size = len(payload)

        if compress_zstd:
            if zstd is None:
                raise RuntimeError(
                    "zstandard is required for zstd compression. \
                    Install with `pip install neurosim[zstd]`."
                )

            compressor = zstd.ZstdCompressor(
                level=zstd_level,
                write_checksum=True,
                write_content_size=True,
            )
            payload = compressor.compress(payload)
            compressed_size = len(payload)
            content_type = "application/zstd"
            content_encoding = None
            action_desc = "JSON upload (zstd-compressed)"
            action_desc = f"JSON upload (zstd-compressed: \
                {original_size} -> {compressed_size} bytes)"

        else:
            content_type = "application/json; charset=utf-8"
            content_encoding = None
            action_desc = "JSON upload"

        return self._upload_bytes(
            data=payload,
            blob_path=blob_path,
            content_type=content_type,
            content_encoding=content_encoding,
            make_public=make_public,
            action_desc=action_desc,
        )

    def download_zstd_json(self, blob_path: str) -> Mapping[str, Any] | Any:
        """Download ZSTD-compressed JSON from GCS.

        Args:
            blob_path: Path to the zstd-compressed JSON file in GCS.
                      If it doesn't end with .zst, the extension will be added.

        Returns:
            The decompressed JSON data.
        """
        if zstd is None:
            raise RuntimeError(
                "zstandard is required for zstd decompression. "
                "Install with `pip install neurosim[zstd]`."
            )

        # Ensure .zst extension
        if not blob_path.endswith('.zst'):
            blob_path = blob_path + '.zst'

        # Download the compressed data as bytes
        compressed_data = self._client.bucket(
            self.bucket_name).blob(blob_path).download_as_bytes()

        # Decompress the data
        decompressor = zstd.ZstdDecompressor()
        decompressed_data = decompressor.decompress(compressed_data)

        # Parse as JSON
        return json.loads(decompressed_data.decode('utf-8'))

    def download_json(self, blob_path: str) -> Mapping[str, Any] | Any:
        """Download regular JSON from GCS.

        Args:
            blob_path: Path to the JSON file in GCS.

        Returns:
            The parsed JSON data.

        Raises:
            FileNotFoundError: If the blob doesn't exist in GCS.
            json.JSONDecodeError: If the file content is not valid JSON.
            UnicodeDecodeError: If the file content is not valid UTF-8.
        """
        try:
            bucket = self._client.bucket(self.bucket_name)
            blob = bucket.blob(blob_path)

            # Check if blob exists
            if not blob.exists():
                raise FileNotFoundError(
                    f"File not found in GCS: gs://{self.bucket_name}/{blob_path}")

            # Download the JSON data as bytes
            json_data = blob.download_as_bytes()

            # Parse as JSON
            return json.loads(json_data.decode('utf-8'))

        except Exception as e:
            logger.error(
                "Failed to download JSON from gs://%s/%s: %s",
                self.bucket_name, blob_path, str(e)
            )
            raise

    def download_png(self, blob_path: str) -> bytes:
        """Download PNG from GCS."""
        return self._client.bucket(self.bucket_name).blob(blob_path).download_as_bytes()


__all__ = [
    "GCSUploader",
]


def _build_arg_parser() -> argparse.ArgumentParser:
    """Build and return the CLI argument parser for uploads."""
    parser = argparse.ArgumentParser(
        description="Upload JSON or PNG to Google Cloud Storage")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # JSON subcommand
    json_parser = subparsers.add_parser("json", help="Upload JSON data")
    json_parser.add_argument(
        "blob", help="GCS blob path (e.g., path/to/file.json)")
    json_source = json_parser.add_mutually_exclusive_group(required=True)
    json_source.add_argument("--data", help="Inline JSON string to upload")
    json_source.add_argument("--data-file", type=Path,
                             help="Path to a JSON file to upload")
    json_parser.add_argument(
        "--compress-zstd", action="store_true", help="Compress JSON with zstd")
    json_parser.add_argument("--zstd-level", type=int, default=3,
                             help="Zstandard compression level (default: 3)")
    json_parser.add_argument(
        "--make-public", action="store_true", help="Make the object publicly readable")
    json_parser.add_argument(
        "--bucket", help="Override GCS bucket name (defaults to env GCS_BUCKET_NAME)")

    # PNG subcommand
    png_parser = subparsers.add_parser("png", help="Upload PNG bytes")
    png_parser.add_argument(
        "blob", help="GCS blob path (e.g., path/to/image.png)")
    png_parser.add_argument(
        "file", type=Path, help="Path to a PNG file to upload")
    png_parser.add_argument(
        "--make-public", action="store_true", help="Make the object publicly readable")
    png_parser.add_argument(
        "--bucket", help="Override GCS bucket name (defaults to env GCS_BUCKET_NAME)")

    return parser


def _run_cli():
    """Run the CLI and return an appropriate exit code."""
    logging.basicConfig(level=logging.INFO,
                        format="%(levelname)s %(name)s: %(message)s")
    parser = _build_arg_parser()
    args = parser.parse_args()

    uploader = GCSUploader(bucket_name=getattr(args, "bucket", None))

    if args.command == "json":
        if args.data_file is not None:
            payload = json.loads(args.data_file.read_text(encoding="utf-8"))
            desc_source = f"file={args.data_file}"
        else:
            payload = json.loads(args.data)
            desc_source = "inline --data"

        bucket_name = uploader.bucket_name
        logger.info(
            "CLI: JSON upload requested (bucket=%s, blob=%s, %s, compress_zstd=%s)",
            bucket_name,
            args.blob,
            desc_source,
            args.compress_zstd,
        )
        uri = uploader.upload_json(
            blob_path=args.blob,
            data=payload,
            make_public=args.make_public,
            compress_zstd=bool(args.compress_zstd),
            zstd_level=int(args.zstd_level),
        )
        print(uri)

    if args.command == "png":
        data = args.file.read_bytes()
        bucket_name = uploader.bucket_name
        logger.info(
            "CLI: PNG upload requested (bucket=%s, blob=%s, file=%s)",
            bucket_name,
            args.blob,
            args.file,
        )
        uri = uploader.upload_png(
            data=data, blob_path=args.blob, make_public=args.make_public)
        print(uri)

    parser.error("Unknown command")


if __name__ == "__main__":  # pragma: no cover - CLI utility
    raise SystemExit(_run_cli())
