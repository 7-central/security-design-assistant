#!/bin/bash

# Setup GitHub Secrets for CI/CD Pipeline
# This script uses GitHub CLI to configure repository secrets

set -e

echo "🔐 Setting up GitHub Secrets for security-design-assistant"
echo "=================================================="

# Check if gh CLI is installed
if ! command -v gh &> /dev/null; then
    echo "❌ GitHub CLI (gh) is not installed"
    echo "Install it with: brew install gh"
    exit 1
fi

# Check if authenticated
if ! gh auth status &> /dev/null; then
    echo "❌ Not authenticated with GitHub"
    echo "Run: gh auth login"
    exit 1
fi

# Set repository
REPO="7-central/security-design-assistant"
echo "📦 Repository: $REPO"

# Function to safely set a secret
set_secret() {
    local secret_name=$1
    local secret_value=$2
    local description=$3
    
    echo ""
    echo "Setting $secret_name - $description"
    
    if [ -z "$secret_value" ]; then
        echo "⚠️  Skipping $secret_name (no value provided)"
        return
    fi
    
    echo "$secret_value" | gh secret set "$secret_name" --repo="$REPO"
    echo "✅ $secret_name configured"
}

# Get AWS credentials
echo ""
echo "📋 AWS Credentials Setup"
echo "------------------------"
echo "You'll need the credentials from the 7c-IAM-Admin-User"
echo ""

# Check if we can get credentials from AWS CLI
if aws configure get aws_access_key_id --profile design &> /dev/null; then
    echo "Found AWS profile 'design' - using those credentials"
    AWS_KEY=$(aws configure get aws_access_key_id --profile design)
    AWS_SECRET=$(aws configure get aws_secret_access_key --profile design)
else
    echo "Enter AWS credentials manually:"
    read -p "AWS Access Key ID: " AWS_KEY
    read -s -p "AWS Secret Access Key: " AWS_SECRET
    echo ""
fi

# Get Gemini API key
echo ""
echo "📋 Gemini API Key Setup"
echo "-----------------------"
echo "Get your key from: https://aistudio.google.com/app/apikey"
echo ""

# Try to get from .env file first
if [ -f .env ] && grep -q "GEMINI_API_KEY=" .env; then
    GEMINI_KEY=$(grep "GEMINI_API_KEY=" .env | cut -d'=' -f2)
    echo "Found Gemini API key in .env file"
else
    read -s -p "Gemini API Key: " GEMINI_KEY
    echo ""
fi

# Confirm before setting
echo ""
echo "📝 Summary"
echo "----------"
echo "Repository: $REPO"
echo "AWS Access Key ID: ${AWS_KEY:0:10}..."
echo "AWS Secret: ***hidden***"
echo "Gemini API Key: ${GEMINI_KEY:0:10}..."
echo "AWS Region: eu-west-2 (will be set)"
echo ""
read -p "Proceed with setting these secrets? (y/n) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Cancelled"
    exit 1
fi

# Set the secrets
echo ""
echo "🚀 Setting GitHub Secrets..."
echo "============================"

set_secret "AWS_ACCESS_KEY_ID" "$AWS_KEY" "AWS Access Key ID from 7c-IAM-Admin-User"
set_secret "AWS_SECRET_ACCESS_KEY" "$AWS_SECRET" "AWS Secret Access Key from 7c-IAM-Admin-User"
set_secret "AWS_REGION" "eu-west-2" "AWS Region for deployment"
set_secret "GEMINI_API_KEY" "$GEMINI_KEY" "Google GenAI API Key"

# Verify secrets were set
echo ""
echo "🔍 Verifying secrets..."
echo "========================"
gh secret list --repo="$REPO"

echo ""
echo "✅ GitHub Secrets configuration complete!"
echo ""
echo "Next steps:"
echo "1. Create and push to dev branch to trigger CI/CD:"
echo "   git checkout -b dev"
echo "   git add ."
echo "   git commit -m 'feat: add E2E test infrastructure and CI/CD pipeline'"
echo "   git push -u origin dev"
echo ""
echo "2. Check GitHub Actions at:"
echo "   https://github.com/$REPO/actions"
echo ""
echo "3. (Optional) Configure branch protection rules at:"
echo "   https://github.com/$REPO/settings/branches"