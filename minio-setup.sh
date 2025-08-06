#!/bin/sh

# Set alias to local MinIO instance
mc alias set local http://localhost:9000 ROOTUSER POSTUREX

# Create bucket if it doesn't exist
mc mb local/videos || true

# Enable webhook notifications
mc admin config set local notify_webhook:1 endpoint="http://flask-app:5000/api/minio/webhook" || true

# Add notification on PUT (upload) events
mc event add local/videos arn:minio:sqs::1:webhook --event put || true
