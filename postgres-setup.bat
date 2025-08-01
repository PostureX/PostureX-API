@echo off
echo [INFO] Starting PostgreSQL container...

docker run --name posturex-postgres ^
  -e POSTGRES_USER=postgres ^
  -e POSTGRES_PASSWORD=postgres ^
  -e POSTGRES_DB=posturex ^
  -p 5432:5432 ^
  -v posturex_pgdata:/var/lib/postgresql/data ^
  -d postgres

echo [INFO] PostgreSQL container started with:
echo [INFO]   Username: postgres
echo [INFO]   Password: postgres
echo [INFO]   Database: posturex
echo [INFO]