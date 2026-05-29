#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

echo "======================================"
echo "Supabase Database Dump & Restore Tool"
echo "======================================"

if [ "$#" -ne 2 ]; then
    echo "Usage: $0 <source_db_pooling_url> <target_db_pooling_url>"
    echo ""
    echo "Example:"
    echo "  $0 \"postgres://postgres.[PROJECT-REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres\" \"postgres://postgres.[PROJECT-REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres\""
    exit 1
fi

SOURCE_POOLING_URL=$1
TARGET_POOLING_URL=$2
DUMP_FILE="supabase_dump_$(date +%Y%m%d_%H%M%S).sql"

echo "[1/3] Dumping from source database..."
# Note: --clean removes existing objects before creating them
# --no-owner and --no-privileges are often needed for Supabase to avoid role-related errors
pg_dump "$SOURCE_POOLING_URL" \
    --clean \
    --if-exists \
    --no-owner \
    --no-privileges \
    --quote-all-identifiers \
    --file="$DUMP_FILE"

echo "[2/3] Source database dumped successfully to $DUMP_FILE"

echo "[3/3] Restoring to target database..."
psql "$TARGET_POOLING_URL" < "$DUMP_FILE"

echo "======================================"
echo "Migration completed successfully!"
echo "======================================"

# Optional: Clean up the dump file (uncomment to enable)
# echo "Cleaning up dump file..."
# rm "$DUMP_FILE"
