#!/bin/sh

# Set alias to local MinIO instance
mc alias set local http://localhost:9000 ROOTUSER POSTUREX

# Create bucket if it doesn't exist
mc mb --ignore-existing local/videos

# Add notification on PUT (upload) events
mc event add local/videos arn:minio:sqs::1:webhook --event put
