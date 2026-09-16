"""Initialize the artifact bucket and start the tracking server."""

import os
import time

import boto3
from botocore.exceptions import ClientError, EndpointConnectionError


def main():
    client = boto3.client("s3", endpoint_url=os.environ["MLFLOW_S3_ENDPOINT_URL"])
    for attempt in range(30):
        try:
            client.head_bucket(Bucket="mlflow")
            break
        except ClientError as error:
            if error.response["ResponseMetadata"]["HTTPStatusCode"] == 404:
                client.create_bucket(Bucket="mlflow")
                break
            raise
        except EndpointConnectionError:
            if attempt == 29:
                raise
            time.sleep(2)
    # Passwords stay in environment; they are not command-line arguments.
    os.environ["MLFLOW_BACKEND_STORE_URI"] = (
        "postgresql+psycopg2://mlflow:" + os.environ["POSTGRES_PASSWORD"] + "@postgres:5432/mlflow"
    )
    os.execvp(
        "mlflow",
        [
            "mlflow",
            "server",
            "--host",
            "0.0.0.0",
            "--port",
            "5000",
            "--artifacts-destination",
            "s3://mlflow",
            "--serve-artifacts",
            "--workers",
            "1",
            "--allowed-hosts",
            "mlflow,mlflow:5000,localhost:*,127.0.0.1:*",
        ],
    )


if __name__ == "__main__":
    main()
