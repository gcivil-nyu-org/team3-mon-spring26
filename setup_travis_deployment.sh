#!/bin/bash

# Setup script for Travis CI deployment to Elastic Beanstalk
# This script provides instructions for configuring Travis CI

echo "🚀 Travis CI Deployment Setup Guide"
echo "=========================================="
echo ""

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI is not installed. Please install it first:"
    echo "   pip install awscli"
    exit 1
fi

# Check if user is logged in to AWS
echo "🔑 Checking AWS credentials..."
if ! aws sts get-caller-identity &> /dev/null; then
    echo "❌ AWS credentials not configured. Run: aws configure"
    exit 1
fi

echo "✅ AWS credentials verified"
echo ""

# Verify S3 bucket exists
echo "📦 Verifying S3 bucket: nomz-static-files"
if aws s3 ls s3://nomz-static-files 2>/dev/null; then
    echo "✅ S3 bucket verified"
else
    echo "❌ S3 bucket nomz-static-files not found"
    exit 1
fi

echo ""
echo "=========================================="
echo "✅ PRE-SETUP VERIFICATION COMPLETE!"
echo "=========================================="
echo ""
echo "📋 NEXT STEPS - Add these to Travis CI:"
echo ""
echo "Go to: https://app.travis-ci.com/account/repositories"
echo "Select your repository → Settings → Environment Variables"
echo ""
echo "Add these 2 environment variables:"
echo "  1. AWS_ACCESS_KEY_ID = YOUR_AWS_ACCESS_KEY_ID"
echo "  2. AWS_SECRET_ACCESS_KEY = YOUR_AWS_SECRET_ACCESS_KEY"
echo ""
echo "⚠️  IMPORTANT: Mark AWS_SECRET_ACCESS_KEY as PRIVATE"
echo ""
echo "Bucket being used: nomz-static-files"
echo "Deployment path: deployments/"
echo ""
echo "Then push to production branch to test:"
echo "  git push origin production"
echo ""
