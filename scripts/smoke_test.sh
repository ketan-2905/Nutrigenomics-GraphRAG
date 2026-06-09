#!/usr/bin/env bash
set -e

API_URL="${API_URL:-http://127.0.0.1:8000}"
PASS=0
FAIL=0

log_ok()   { echo "[PASS] $1"; PASS=$((PASS+1)); }
log_fail() { echo "[FAIL] $1"; FAIL=$((FAIL+1)); }

echo "============================================"
echo " Nutrigenomics GraphRAG — Smoke Test"
echo "============================================"

# 1. Start Docker services
echo ""
echo "Step 1: Starting Neo4j and Redis..."
docker compose up -d neo4j redis
echo "  Waiting 15 s for Neo4j to be ready..."
sleep 15

# 2. Load seed data
echo ""
echo "Step 2: Loading seed data..."
python -m src.ingestion.load_seed_data && log_ok "Seed data loaded" || log_fail "Seed data load failed"

# 3. Build Chroma index
echo ""
echo "Step 3: Building Chroma vector index..."
python -m src.rag.embed_chunks && log_ok "Chroma index built" || log_fail "Chroma index build failed"

# 4. Start API in background
echo ""
echo "Step 4: Starting FastAPI in background..."
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 &
API_PID=$!
echo "  API PID: $API_PID — waiting 5 s..."
sleep 5

cleanup() {
    echo ""
    echo "Stopping API (PID $API_PID)..."
    kill "$API_PID" 2>/dev/null || true
}
trap cleanup EXIT

# 5. /health
echo ""
echo "Step 5: GET /health"
HEALTH=$(curl -sf "$API_URL/health") && log_ok "/health OK: $HEALTH" || log_fail "/health failed"

# 6. /ask
echo ""
echo "Step 6: POST /ask"
ASK=$(curl -sf -X POST "$API_URL/ask" \
    -H "Content-Type: application/json" \
    -d '{"question":"What foods may support rs1801133 related folate metabolism risk?"}')
if echo "$ASK" | python -c "import sys, json; d=json.load(sys.stdin); assert 'answer' in d" 2>/dev/null; then
    log_ok "/ask OK"
else
    log_fail "/ask response missing 'answer' field: $ASK"
fi

# 7. /metrics
echo ""
echo "Step 7: GET /metrics"
METRICS=$(curl -sf "$API_URL/metrics")
if echo "$METRICS" | grep -q "rag_requests_total"; then
    log_ok "/metrics OK (rag_requests_total present)"
else
    log_fail "/metrics missing rag_requests_total"
fi

# Summary
echo ""
echo "============================================"
echo " Smoke test summary"
echo "   PASS: $PASS"
echo "   FAIL: $FAIL"
echo "============================================"

[ "$FAIL" -eq 0 ] && exit 0 || exit 1
