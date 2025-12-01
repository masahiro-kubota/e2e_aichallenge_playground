"""S3/MinIO storage abstraction for dataset management."""

import os
from pathlib import Path
from typing import Literal

import boto3
from botocore.client import Config


class DatasetStorage:
    """Dataset storage abstraction for S3/MinIO."""

    def __init__(
        self,
        endpoint_url: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        region: str = "us-east-1",
    ) -> None:
        """Initialize S3 client.

        Args:
            endpoint_url: S3 endpoint URL (for MinIO)
            access_key: AWS access key ID
            secret_key: AWS secret access key
            region: AWS region
        """
        # Load environment variables from .env file
        from dotenv import load_dotenv

        load_dotenv()

        # Use environment variables if not provided
        self.endpoint_url = endpoint_url or os.getenv("AWS_ENDPOINT_URL")
        self.access_key = access_key or os.getenv("AWS_ACCESS_KEY_ID", "minioadmin")
        self.secret_key = secret_key or os.getenv("AWS_SECRET_ACCESS_KEY", "minioadmin")
        self.region = region or os.getenv("AWS_REGION", "us-east-1")

        # Initialize S3 client
        self.s3_client = boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name=self.region,
            config=Config(signature_version="s3v4"),
        )

    def build_dataset_path(
        self,
        project: str,
        scenario: str,
        version: str,
        stage: Literal["raw", "processed", "features"],
    ) -> str:
        """Build S3 dataset path.

        Args:
            project: Project name (e.g., "e2e_aichallenge")
            scenario: Scenario/task name (e.g., "pure_pursuit")
            version: Dataset version (e.g., "v1.0")
            stage: Data processing stage

        Returns:
            S3 path (e.g., "s3://datasets/e2e_aichallenge/pure_pursuit/v1.0/raw/")
        """
        return f"s3://datasets/{project}/{scenario}/{version}/{stage}/"

    def parse_s3_path(self, s3_path: str) -> tuple[str, str]:
        """Parse S3 path into bucket and key.

        Args:
            s3_path: S3 path (e.g., "s3://datasets/path/to/file.json")

        Returns:
            Tuple of (bucket, key)
        """
        if not s3_path.startswith("s3://"):
            raise ValueError(f"Invalid S3 path: {s3_path}")

        path_without_prefix = s3_path[5:]  # Remove "s3://"
        parts = path_without_prefix.split("/", 1)

        bucket = parts[0]
        key = parts[1] if len(parts) > 1 else ""

        return bucket, key

    def upload_file(self, local_path: Path, s3_path: str) -> None:
        """Upload file to S3.

        Args:
            local_path: Local file path
            s3_path: S3 destination path
        """
        bucket, key = self.parse_s3_path(s3_path)

        print(f"Uploading {local_path} to {s3_path}")
        self.s3_client.upload_file(str(local_path), bucket, key)

    def download_file(self, s3_path: str, local_path: Path) -> None:
        """Download file from S3.

        Args:
            s3_path: S3 source path
            local_path: Local destination path
        """
        bucket, key = self.parse_s3_path(s3_path)

        local_path.parent.mkdir(parents=True, exist_ok=True)
        print(f"Downloading {s3_path} to {local_path}")
        self.s3_client.download_file(bucket, key, str(local_path))

    def list_files(self, s3_path: str, pattern: str = "*.json") -> list[str]:
        """List files in S3 path.

        Args:
            s3_path: S3 directory path
            pattern: File pattern (e.g., "*.json")

        Returns:
            List of S3 file paths
        """
        import fnmatch

        bucket, prefix = self.parse_s3_path(s3_path)

        # Ensure prefix ends with /
        if prefix and not prefix.endswith("/"):
            prefix += "/"

        response = self.s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix)

        if "Contents" not in response:
            return []

        files = []
        for obj in response["Contents"]:
            key = obj["Key"]
            filename = key.split("/")[-1]

            if fnmatch.fnmatch(filename, pattern):
                files.append(f"s3://{bucket}/{key}")

        return files

    def ensure_bucket_exists(self, bucket: str) -> None:
        """Ensure S3 bucket exists, create if not.

        Args:
            bucket: Bucket name
        """
        try:
            self.s3_client.head_bucket(Bucket=bucket)
        except Exception:
            print(f"Creating bucket: {bucket}")
            self.s3_client.create_bucket(Bucket=bucket)
