from datetime import datetime
import io
import json
import boto3
from botocore.config import Config
from typing import Optional, Tuple
from botocore.exceptions import ClientError

from logger_service import LoggerService

from common import os, load_dotenv


class AWSService:
    USED_LINK_KEY = "used_affiliate_links"

    def __init__(self):
        self.logger_service = LoggerService(name=self.__class__.__name__)
        self.region_name = os.getenv("AWS_REGION", "us-east-1")
        self.access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
        self.secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        self.ses_client = boto3.client(
            "ses",
            region_name=self.region_name,
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
        )
        session = boto3.Session(
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
            region_name=self.region_name,
        )
        self.s3_client = session.client(
            "s3",
            endpoint_url=f"https://s3.{self.region_name}.amazonaws.com",  # Explicit endpoint
            config=Config(
                connect_timeout=60,
                read_timeout=60,
                retries={
                    "max_attempts": 5,
                    "mode": "standard",
                },
                tcp_keepalive=True,
                max_pool_connections=10,
            ),
        )
        self.bucket_name = os.getenv("AWS_S3_BUCKET")

    def get_string_from_s3(
        self, key: str, file_format: str = "txt", try_count: int = 3
    ) -> Optional[Tuple[str, datetime]]:
        """
        Retrieve a string and creation date from an S3 bucket object.
        Returns a tuple of (content, last_modified_date) or None if retrieval fails.
        """
        try:
            # Validate inputs
            if not key:
                self.logger_service.warning(
                    "No S3 key provided, cannot retrieve content"
                )
                return None, None

            # Retrieve object from S3
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=key)
            content = response["Body"].read().decode("utf-8")
            last_modified = response[
                "LastModified"
            ]  # Extract creation/last modified date

            # Validate JSON if specified
            if file_format == "json":
                try:
                    json.loads(content)
                except json.JSONDecodeError as e:
                    self.logger_service.error(
                        f"Invalid JSON content in s3://{self.bucket_name}/{key}: {str(e)}"
                    )
                    return None, None

            return content, last_modified if content else (None, None)

        except ClientError as e:
            if try_count > 0:
                return self.get_string_from_s3(
                    key=key, file_format=file_format, try_count=try_count - 1
                )
            else:
                error_code = e.response["Error"]["Code"]
                if error_code == "NoSuchKey":
                    self.logger_service.warning(
                        f"S3 object not found: s3://{self.bucket_name}/{key}"
                    )
                else:
                    self.logger_service.error(f"Failed to retrieve from S3: {str(e)}")
                return None, None
        except Exception as e:
            if try_count > 0:
                self.logger_service.info("retrying get_string_from_s3")
                return self.get_string_from_s3(
                    key=key, file_format=file_format, try_count=try_count - 1
                )
            else:
                self.logger_service.error(
                    f"Unexpected error during S3 retrieval: {str(e)}"
                )
                return None, None

    def upload_string_to_s3(
        self,
        content: str,
        key: str,
        file_format: str = "txt",
    ) -> bool:
        """
        Upload a string to an S3 bucket as a text file or other format.
        """
        try:
            # Validate inputs
            if not content:
                self.logger_service.warning("Empty string provided, skipping upload")
                return False

            # Prepare content
            if file_format == "json":
                # Ensure content is valid JSON
                try:
                    json.loads(content)
                except json.JSONDecodeError:
                    self.logger_service.error("Invalid JSON content provided")
                    return False
                buffer = io.BytesIO(content.encode("utf-8"))
                content_type = "application/json"
            else:  # txt
                buffer = io.BytesIO(content.encode("utf-8"))
                content_type = "text/plain"

            buffer.seek(0)

            # Upload to S3
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=buffer,
                ContentType=content_type,
            )
            return True

        except ClientError as e:
            self.logger_service.error(f"Failed to upload string to S3: {str(e)}")
            return False
        except Exception as e:
            self.logger_service.error(f"Unexpected error during S3 upload: {str(e)}")
            return False

    def get_used_affiliate_links(self) -> list[str]:
        content, _ = self.get_string_from_s3(key=self.USED_LINK_KEY, file_format="json")

        if content is None:
            self.logger_service.info(
                "No used affiliate links found in S3 or retrieval failed"
            )
            return []

        try:
            used_links = json.loads(content)  # Deserialize JSON to list
            # Verify it's a list of strings
            if not isinstance(used_links, list) or not all(
                isinstance(item, str) for item in used_links
            ):
                self.logger_service.error(
                    "Invalid format for used_links: not a list of strings"
                )
                return []
            return used_links
        except json.JSONDecodeError as e:
            self.logger_service.error(f"Failed to parse JSON from used_links: {str(e)}")
            return []

    def add_used_affiliate_links(self, links: list[str]) -> list[str]:
        try:
            content = json.dumps(links)
            success = self.upload_string_to_s3(
                content=content,
                key=self.USED_LINK_KEY,
                file_format="json",
            )
            return success
        except Exception as e:
            self.logger_service.error(f"Error writing affiliate link to S3: {str(e)}")
            return False

    def clear_used_affiliate_links(self) -> bool:
        """
        Clear all used affiliate links by deleting the S3 object.
        """
        return self.delete_s3_object(key=self.USED_LINK_KEY)

    def delete_s3_object(self, key: str) -> bool:
        """
        Delete a specific object from an S3 bucket by its key.
        """
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=key)
            self.logger_service.info(f"Deleted object {key}")
            return True

        except ClientError as e:
            self.logger_service.error(
                f"Failed to delete object {key} from bucket {self.bucket_name}: {str(e)}"
            )
            return False
        except Exception as e:
            self.logger_service.error(
                f"Unexpected error during object deletion: {str(e)}"
            )
            return False


if __name__ == "__main__":
    service = AWSService()
    service.clear_used_affiliate_links()
