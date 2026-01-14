#!/bin/bash

# Deployment script for Google Cloud Run
# This script helps you deploy your application to Google Cloud Run

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
SERVICE_NAME="shopify-quantity-service"
REGION="europe-west6"
MEMORY="512Mi"
CPU="1"
MAX_INSTANCES="10"
MIN_INSTANCES="0"
TIMEOUT="300s"

echo -e "${GREEN}=== Google Cloud Run Deployment Script ===${NC}\n"

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}Error: gcloud CLI is not installed${NC}"
    echo "Please install it from: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Get current project
PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}Error: No GCP project configured${NC}"
    echo "Run: gcloud config set project YOUR_PROJECT_ID"
    exit 1
fi

echo -e "${GREEN}Project ID:${NC} $PROJECT_ID"
echo -e "${GREEN}Service Name:${NC} $SERVICE_NAME"
echo -e "${GREEN}Region:${NC} $REGION\n"

# Confirm deployment
read -p "Do you want to proceed with deployment? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Deployment cancelled${NC}"
    exit 0
fi

echo -e "\n${GREEN}Step 1: Building and deploying to Cloud Run...${NC}"

gcloud run deploy $SERVICE_NAME \
    --source . \
    --region=$REGION \
    --platform=managed \
    --memory=$MEMORY \
    --cpu=$CPU \
    --max-instances=$MAX_INSTANCES \
    --min-instances=$MIN_INSTANCES \
    --timeout=$TIMEOUT

if [ $? -eq 0 ]; then
    echo -e "\n${GREEN}✓ Deployment successful!${NC}\n"
    
    # Get service URL
    SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region=$REGION --format='value(status.url)')
    
    echo -e "${GREEN}Service URL:${NC} $SERVICE_URL"
    echo -e "${GREEN}API Docs:${NC} $SERVICE_URL/docs"
    echo -e "\n${YELLOW}Note: If you need environment variables, add them using:${NC}"
    echo "gcloud run services update $SERVICE_NAME --region=$REGION --set-env-vars KEY=VALUE"
else
    echo -e "\n${RED}✗ Deployment failed${NC}"
    exit 1
fi
