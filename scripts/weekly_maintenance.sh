#!/bin/bash
# NeuralMind Weekly Maintenance Script
# Schedule: Every Monday at 3 AM (or run manually)
# Usage: ./scripts/weekly_maintenance.sh /path/to/project

set -e

# Configuration
PROJECT_PATH="${1:-.}"
LOG_FILE="/tmp/neuralmind_maintenance_$(date +%Y%m%d_%H%M%S).log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "================================================================" | tee -a "$LOG_FILE"
echo "🧠 NEURALMIND WEEKLY MAINTENANCE REPORT" | tee -a "$LOG_FILE"
echo "================================================================" | tee -a "$LOG_FILE"
echo "Project: $PROJECT_PATH" | tee -a "$LOG_FILE"
echo "Date: $(date '+%Y-%m-%d %H:%M:%S')" | tee -a "$LOG_FILE"
echo "================================================================" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# Navigate to project
cd "$PROJECT_PATH" || { echo -e "${RED}Error: Cannot access project directory${NC}"; exit 1; }

# Step 1: Check current status
echo -e "${BLUE}[1/5] Checking current status...${NC}" | tee -a "$LOG_FILE"
if command -v neuralmind &> /dev/null; then
    STATS_BEFORE=$(neuralmind stats . 2>/dev/null || echo "No existing index")
    echo "Before: $STATS_BEFORE" | tee -a "$LOG_FILE"
else
    echo -e "${RED}Error: neuralmind not found. Install with: pip install neuralmind${NC}" | tee -a "$LOG_FILE"
    exit 1
fi

# Step 2: Update knowledge graph
echo -e "${BLUE}[2/5] Updating knowledge graph...${NC}" | tee -a "$LOG_FILE"
if command -v graphify &> /dev/null; then
    graphify update . 2>&1 | tee -a "$LOG_FILE"
    GRAPHIFY_STATUS=$?
    if [ $GRAPHIFY_STATUS -eq 0 ]; then
        echo -e "${GREEN}✓ Knowledge graph updated${NC}" | tee -a "$LOG_FILE"
    else
        echo -e "${YELLOW}⚠ Graphify completed with warnings${NC}" | tee -a "$LOG_FILE"
    fi
else
    echo -e "${YELLOW}⚠ graphify not found. Skipping graph update.${NC}" | tee -a "$LOG_FILE"
fi

# Step 3: Rebuild neural index
echo -e "${BLUE}[3/5] Rebuilding neural index...${NC}" | tee -a "$LOG_FILE"
START_TIME=$(date +%s)
neuralmind build . 2>&1 | tee -a "$LOG_FILE"
END_TIME=$(date +%s)
BUILD_DURATION=$((END_TIME - START_TIME))
echo -e "${GREEN}✓ Index rebuilt in ${BUILD_DURATION}s${NC}" | tee -a "$LOG_FILE"

# Step 4: Get updated stats
echo -e "${BLUE}[4/5] Getting updated statistics...${NC}" | tee -a "$LOG_FILE"
neuralmind stats . 2>&1 | tee -a "$LOG_FILE"

# Step 5: Run benchmark
echo -e "${BLUE}[5/5] Running token benchmark...${NC}" | tee -a "$LOG_FILE"
neuralmind benchmark . 2>&1 | tee -a "$LOG_FILE"

# Summary
echo "" | tee -a "$LOG_FILE"
echo "================================================================" | tee -a "$LOG_FILE"
echo "📊 MAINTENANCE SUMMARY" | tee -a "$LOG_FILE"
echo "================================================================" | tee -a "$LOG_FILE"
echo "Status: SUCCESS" | tee -a "$LOG_FILE"
echo "Build time: ${BUILD_DURATION}s" | tee -a "$LOG_FILE"
echo "Log file: $LOG_FILE" | tee -a "$LOG_FILE"
echo "================================================================" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"
echo -e "${GREEN}✅ Weekly maintenance complete!${NC}" | tee -a "$LOG_FILE"
