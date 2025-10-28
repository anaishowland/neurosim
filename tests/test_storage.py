"""Tests for neurosim.core.storage module."""

import json
import os
from unittest.mock import Mock, patch
from typing import Dict, Any
import pytest

from src.neurosim.core.storage import GCSUploader


class TestGCSUploaderUploadJson:
    """Test cases for GCSUploader.upload_json method."""

    mock_client: Mock
    mock_bucket: Mock
    mock_blob: Mock
    uploaded_data: Dict[str, Any]
    uploader: GCSUploader

    def setup_method(self):
        """Set up test fixtures before each test method."""
        # Create mock GCS client and related objects
        self.mock_client = Mock()
        self.mock_bucket = Mock()
        self.mock_blob = Mock()

        self.mock_client.bucket.return_value = self.mock_bucket
        self.mock_bucket.blob.return_value = self.mock_blob

        # Track upload calls
        self.uploaded_data = {}

        def capture_upload(data, content_type=None):
            self.uploaded_data['data'] = data
            self.uploaded_data['content_type'] = content_type
            self.uploaded_data['size'] = len(data)

        self.mock_blob.upload_from_string.side_effect = capture_upload

        # Create uploader instance
        self.uploader = GCSUploader(
            client=self.mock_client, bucket_name="test-bucket")

    def test_upload_json_without_compression(self):
        """Test JSON upload without zstd compression."""
        test_data = {"key": "value", "number": 42}
        blob_path = "test/data.json"

        result = self.uploader.upload_json(
            blob_path=blob_path,
            data=test_data,
            compress_zstd=False
        )

        # Verify the upload was called with correct parameters
        assert self.mock_client.bucket.called
        assert self.mock_bucket.blob.called_with(blob_path)
        assert self.mock_blob.upload_from_string.called

        # Check uploaded data
        expected_json = json.dumps(
            test_data, ensure_ascii=False).encode("utf-8")
        assert self.uploaded_data['data'] == expected_json
        assert self.uploaded_data['content_type'] == "application/json; charset=utf-8"

        # Check return value
        assert result == f"gs://test-bucket/{blob_path}"

        # Note: We skip checking if content_encoding was not set because
        # Mock objects create attributes when accessed, making it hard to test negative cases.
        # The important part is that the correct content_type was used for uncompressed data.

    def test_upload_json_with_compression(self):
        """Test JSON upload with zstd compression."""
        test_data = {
            "jobId": "anthropic",
            "success": False,
            "latency": 58.729464292526245,
            "tokens": [
                {
                    "prompt_tokens": 1042,
                    "completion_tokens": 101,
                    "total_tokens": 1143
                },
                {
                    "prompt_tokens": 1170,
                    "completion_tokens": 143,
                    "total_tokens": 1313
                }
            ],
            "task": {
                "taskId": "walmart2",
                "task": "Find the store hours for the Walmart Supercenter near Dallas, TX (zip code 75201) and also check if the pharmacy has different hours. Only use https://walmart.com to achieve the task. Do not go to any other site. The task is achievable with just navigation from this site.",
                "model": "claude-sonnet-4@20250514"
            },
            "steps": [
                {
                    "state": {
                        "previous_goal_status": "success",
                        "previous_goal_eval": "Navigated to https://walmart.com",
                        "page_summary": "I'll help you find the store hours for a Walmart Supercenter near Dallas, TX (zip code 75201) and check the pharmacy hours. Let me start by opening the Walmart website.",
                        "relevant_interactions": [],
                        "memory": "Navigated to https://walmart.com",
                        "next_goal": ""
                    },
                    "action": {
                        "type": "open_url",
                        "x": None,
                        "y": None,
                        "button": None,
                        "dx": None,
                        "dy": None,
                        "key": None,
                        "text": "https://walmart.com"
                    },
                    "screenshot_path": ""
                }
            ],
            "results": "ERROR: Captcha/verification or no final answer",
            "error": {
                "message": "Captcha/verification or no final answer"
            }
        }
        blob_path = "test/compressed.json"

        result = self.uploader.upload_json(
            blob_path=blob_path,
            data=test_data,
            compress_zstd=True
        )

        # Verify upload was called
        assert self.mock_blob.upload_from_string.called

        # Check content type for compressed data
        assert self.uploaded_data['content_type'] == "application/zstd"

        # Check that content encoding was set
        assert self.mock_blob.content_encoding == "zstd"

        # Verify return value
        assert result == f"gs://test-bucket/{blob_path}"

        # The uploaded data should be compressed (different from raw JSON)
        raw_json = json.dumps(test_data, ensure_ascii=False).encode("utf-8")
        compressed_data = self.uploaded_data['data']

        # Write compressed data to file for inspection
        with open("test.zstd", "wb") as f:
            f.write(compressed_data)

        # Log compression details
        print("\n=== Compression Test Logs ===")
        print(f"Original JSON size: {len(raw_json)} bytes")
        print(f"Compressed data size: {len(compressed_data)} bytes")
        print(
            f"Compression ratio: {len(raw_json) / len(compressed_data):.2f}x")
        print(
            f"Space saved: {((len(raw_json) - len(compressed_data)) / len(raw_json) * 100):.1f}%")
        print(f"Original JSON preview: {raw_json[:50]}...")
        print(f"Compressed data preview: {compressed_data[:20].hex()}...")
        print(f"Content type: {self.uploaded_data['content_type']}")
        print(f"Content encoding: {self.mock_blob.content_encoding}")
        print("Compressed data written to: test.zstd")
        print("============================\n")

        assert compressed_data != raw_json
        # Verify compression actually reduced size
        assert len(compressed_data) < len(raw_json)

    def test_upload_json_compression_levels(self):
        """Test different zstd compression levels."""
        test_data = {"data": "x" * 1000}  # Compressible data

        for level in [1, 3, 9]:
            self.setup_method()  # Reset mocks

            result = self.uploader.upload_json(
                blob_path=f"test/level_{level}.json",
                data=test_data,
                compress_zstd=True,
                zstd_level=level
            )

            assert self.uploaded_data['content_type'] == "application/zstd"
            assert result.startswith("gs://test-bucket/")

    def test_upload_json_make_public(self):
        """Test upload with make_public=True."""
        test_data = {"public": True}

        result = self.uploader.upload_json(
            blob_path="public/data.json",
            data=test_data,
            make_public=True,
            compress_zstd=False
        )

        # Verify make_public was called
        assert self.mock_blob.make_public.called
        assert result.startswith("gs://test-bucket/")

    def test_upload_json_make_public_false(self):
        """Test upload with make_public=False (default)."""
        test_data = {"public": False}

        self.uploader.upload_json(
            blob_path="private/data.json",
            data=test_data,
            make_public=False
        )

        # Verify make_public was NOT called
        assert not self.mock_blob.make_public.called

    def test_upload_json_different_data_types(self):
        """Test upload with different data types."""
        test_cases = [
            {"dict": {"nested": {"value": 1}}},
            ["list", "of", "strings"],
            "simple string",
            42,
            True,
            None,
            {"unicode": "測試", "emoji": "🚀"}
        ]

        for i, test_data in enumerate(test_cases):
            self.setup_method()  # Reset mocks for each test

            result = self.uploader.upload_json(
                blob_path=f"test/type_{i}.json",
                data=test_data,
                compress_zstd=False
            )

            # Verify the data was properly JSON-encoded
            expected_json = json.dumps(
                test_data, ensure_ascii=False).encode("utf-8")
            assert self.uploaded_data['data'] == expected_json
            assert result.startswith("gs://test-bucket/")

    def test_upload_json_bucket_name_from_env(self):
        """Test bucket name resolution from environment variable."""
        with patch.dict(os.environ, {'GCS_BUCKET_NAME': 'env-bucket'}):
            uploader = GCSUploader(client=self.mock_client)

            result = uploader.upload_json(
                blob_path="test.json",
                data={"env": "test"}
            )

            assert result == "gs://env-bucket/test.json"

    def test_upload_json_no_bucket_configured(self):
        """Test error when no bucket is configured."""
        uploader = GCSUploader(
            client=self.mock_client)  # No bucket_name provided

        with patch.dict(os.environ, {}, clear=True):  # Clear env vars
            with pytest.raises(RuntimeError, match="GCS bucket not configured"):
                uploader.upload_json("test.json", {"data": "test"})

    @patch('src.neurosim.core.storage.zstd', None)
    def test_upload_json_missing_zstd_dependency(self):
        """Test error when zstd is not available but compression is requested."""
        with pytest.raises(RuntimeError, match="zstandard is required for zstd compression"):
            self.uploader.upload_json(
                blob_path="test.json",
                data={"test": "data"},
                compress_zstd=True
            )

    def test_upload_json_large_data_compression_efficiency(self):
        """Test that compression actually reduces size for large data."""
        # Create highly compressible data
        large_data = {
            "repeated_data": ["same_value"] * 1000,
            "metadata": {"type": "test", "version": "1.0"}
        }

        # Test without compression
        self.uploader.upload_json(
            blob_path="large_uncompressed.json",
            data=large_data,
            compress_zstd=False
        )
        uncompressed_size = self.uploaded_data['size']

        # Reset and test with compression
        self.setup_method()
        self.uploader.upload_json(
            blob_path="large_compressed.json",
            data=large_data,
            compress_zstd=True
        )
        compressed_size = self.uploaded_data['size']

        # Compression should reduce size significantly
        assert compressed_size < uncompressed_size
        compression_ratio = uncompressed_size / compressed_size
        assert compression_ratio > 1.5  # At least 50% reduction

    def test_upload_json_unicode_handling(self):
        """Test proper Unicode handling in JSON uploads."""
        unicode_data = {
            "chinese": "你好世界",
            "japanese": "こんにちは",
            "emoji": "🌟🚀💎",
            "mixed": "Hello 世界 🌍"
        }

        result = self.uploader.upload_json(
            blob_path="unicode/test.json",
            data=unicode_data,
            compress_zstd=False
        )

        # Verify Unicode was preserved
        uploaded_str = self.uploaded_data['data'].decode('utf-8')
        parsed_data = json.loads(uploaded_str)
        assert parsed_data == unicode_data
        assert result.startswith("gs://test-bucket/")

    def test_upload_json_calls_upload_bytes_with_correct_params(self):
        """Test that upload_json correctly calls _upload_bytes with expected parameters."""
        test_data = {"test": "integration"}
        blob_path = "integration/test.json"

        # Mock _upload_bytes to verify it's called correctly
        with patch.object(self.uploader, '_upload_bytes',
                          return_value="gs://test-bucket/integration/test.json") as mock_upload_bytes:
            result = self.uploader.upload_json(
                blob_path=blob_path,
                data=test_data,
                make_public=True,
                compress_zstd=False
            )

            # Verify _upload_bytes was called with correct arguments
            mock_upload_bytes.assert_called_once()
            call_args = mock_upload_bytes.call_args

            assert call_args.kwargs['blob_path'] == blob_path
            assert call_args.kwargs['content_type'] == "application/json; charset=utf-8"
            assert call_args.kwargs['content_encoding'] is None
            assert call_args.kwargs['make_public'] is True
            assert call_args.kwargs['action_desc'] == "JSON upload"

            # Check that data is properly encoded JSON
            expected_json = json.dumps(
                test_data, ensure_ascii=False).encode("utf-8")
            assert call_args.kwargs['data'] == expected_json

            assert result == "gs://test-bucket/integration/test.json"
