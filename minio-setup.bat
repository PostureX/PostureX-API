docker run -d --name minio-server -p 9000:9000 -p 9001:9001 -e "MINIO_ROOT_USER=ROOTUSER" -e "MINIO_ROOT_PASSWORD=POSTUREX" -v minio_data:/data minio/minio server /data --console-address ":9001"

docker exec minio-server mc alias set local http://localhost:9000 ROOTUSER POSTUREX

docker exec minio-server mc admin config set local notify_webhook:1 endpoint="http://host.docker.internal:5000/api/minio/webhook"

docker exec minio-server mc event add local/videos arn:minio:sqs::1:webhook --event put

docker restart minio-server