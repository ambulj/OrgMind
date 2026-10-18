#!/usr/bin/env bash
set -e

echo "=================================================="
echo " [OrgMind Space] Starting internal FalkorDB Engine"
echo "=================================================="

# Ensure falkordb data dir exists
mkdir -p /tmp/falkordb_data

# Start Redis with FalkorDB module in background
redis-server \
  --dir /tmp/falkordb_data \
  --loadmodule /var/lib/falkordb/bin/falkordb.so \
  --protected-mode no \
  --daemonize yes

# Wait for FalkorDB to be responsive
echo "[OrgMind Space] Waiting for FalkorDB ping..."
MAX_RETRIES=30
RETRY_COUNT=0
until redis-cli ping > /dev/null 2>&1; do
  sleep 0.5
  RETRY_COUNT=$((RETRY_COUNT+1))
  if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
    echo "[ERROR] FalkorDB failed to start in time!"
    exit 1
  fi
done
echo "[OrgMind Space] FalkorDB is ONLINE and ready!"

echo "=================================================="
echo " [OrgMind Space] Seeding Demo Graph (163 nodes)"
echo "=================================================="
python scripts/reset_demo.py

echo "=================================================="
echo " [OrgMind Space] Launching Streamlit on Port 7860"
echo "=================================================="
exec streamlit run apps/legacy-streamlit/streamlit_app.py \
  --server.port 7860 \
  --server.address 0.0.0.0 \
  --server.headless true \
  --server.enableCORS false \
  --server.enableXsrfProtection false \
  --browser.serverAddress 0.0.0.0
