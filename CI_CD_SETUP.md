# CI/CD Setup Guide - Team3 Nomz Project

## Overview
This document explains the CI/CD (Continuous Integration/Continuous Deployment) pipelines for the Nomz project. The setup includes:
- **Automated Testing** on the `develop` branch
- **Automated Deployment** to AWS Elastic Beanstalk on the `production` branch

---

## Workflow Architecture

```
Your Code
    ↓
Push to develop
    ↓
Automated Tests Run (GitHub Actions)
    ├─ Run Django tests
    ├─ Check migrations
    ├─ Code quality checks (flake8, black, isort)
    └─ Collect static files
    ↓
Tests Pass ✅
    ↓
Create Pull Request develop → production
    ↓
Manual Review & Approval
    ↓
Merge to production
    ↓
Automated Deployment (GitHub Actions)
    ├─ Checkout code
    ├─ Install dependencies
    ├─ Run tests one more time
    ├─ Configure AWS credentials
    └─ Deploy to AWS Elastic Beanstalk
    ↓
Live on AWS EB 🚀
```

---

## Step 1: Set Up GitHub Secrets

To deploy to AWS Elastic Beanstalk, GitHub Actions needs your AWS credentials.

### How to Add Secrets:

1. Go to your GitHub repository
2. Navigate to **Settings → Secrets and variables → Actions**
3. Click **New repository secret** and add the following:

| Secret Name | Value |
|---|---|
| `AWS_ACCESS_KEY_ID` | Your AWS Access Key ID |
| `AWS_SECRET_ACCESS_KEY` | Your AWS Secret Access Key |

### Getting AWS Credentials:

1. Log in to your AWS Console
2. Go to **IAM → Users → Your User → Security Credentials**
3. Create an access key if you don't have one
4. Copy the Access Key ID and Secret Access Key
5. **Paste them into GitHub Secrets** (do not commit them to git)

> ⚠️ **IMPORTANT**: Never commit credentials to your repository. Always use GitHub Secrets.

---

## Step 2: Development Workflow

### Local Development
```bash
# 1. Create a new feature branch (optional)
git checkout -b feature/my-feature

# 2. Make your changes
# 3. Test locally:
python manage.py test --no-input

# 4. Commit and push to develop
git add .
git commit -m "Add my feature"
git push origin develop  # or git push origin feature/my-feature
```

### Pull Request to Develop (Optional)
```bash
# Create a PR from your feature branch to develop
# GitHub will automatically run tests
```

### What Happens Automatically:
✅ Tests run against PostgreSQL database  
✅ Migrations are checked  
✅ Code quality checks run (flake8, black, isort)  
✅ Static files collection is tested  

---

## Step 3: Promote to Production

### Once develop is verified:

```bash
# Option 1: Using Git
git checkout develop
git pull origin develop
git checkout -b release/v1.0  # optional: create release branch
git push origin develop

# Option 2: Create a PR in GitHub
# Go to GitHub → Pull Requests
# Click "New Pull Request"
# Select: develop → production
# Add description and create PR
# Get team approval, then merge
```

### Merge develop into production:
```bash
git checkout production
git pull origin production
git merge develop
git push origin production
```

### What Happens Automatically:
1. GitHub Actions triggers the deploy workflow
2. Tests run one final time
3. AWS credentials are loaded from GitHub Secrets
4. Code is deployed to AWS Elastic Beanstalk
5. Application goes live

---

## CI/CD Workflows Explained

### Workflow 1: test.yml (Develop Branch)

**Trigger**: Push to `develop` or Pull Request to `develop`

**Jobs**:
1. **test** - Runs Django tests with PostgreSQL
   - Spins up a test PostgreSQL database
   - Runs migrations
   - Executes all Django tests
   - Checks for unmigrated changes
   - Tests static file collection

2. **code-quality** - Checks code style
   - Black: Checks code formatting
   - isort: Checks import ordering
   - flake8: Lints for errors

---

### Workflow 2: deploy.yml (Production Branch)

**Trigger**: Push to `production`

**Steps**:
1. Checkout code
2. Set up Python environment
3. Install dependencies
4. Run tests (final check)
5. Configure AWS credentials
6. Initialize Elastic Beanstalk CLI
7. Deploy to AWS EB
8. Notify success or failure

---

## Common Scenarios

### Scenario 1: Push Feature to Develop and Tests Fail
1. Check the failed test in GitHub Actions:
   - Go to repository → Actions
   - Click on the failed workflow
   - View the logs
2. Fix the issue locally
3. Commit and push again
4. Tests will rerun automatically

### Scenario 2: Ready to Deploy
1. Ensure `develop` branch has all tested changes
2. Create a PR from `develop` → `production`
3. Get team review
4. Merge the PR
5. Deployment starts automatically
6. Monitor the deployment in GitHub Actions

### Scenario 3: Deployment Fails
1. Check the deployment logs in GitHub Actions
2. Common issues:
   - AWS credentials are invalid → Update GitHub Secrets
   - Migrations failed → Fix locally, push to develop, merge to production
   - Dependencies missing → Add to requirements.txt
3. Fix the issue
4. Push to develop → verify → merge to production

---

## Failure Handling

### If Tests Fail on develop:
- Workflow stops
- No automatic merging to production
- Review the test logs
- Fix the issue
- Push again

### If Deployment Fails on production:
- Application does NOT get deployed
- Previous version stays running
- Check AWS EB console for details
- Fix the issue
- Push to develop → test → merge to production

---

## Environment Variables in Deploy

The `deploy.yml` loads environment variables from AWS Elastic Beanstalk configuration (`.ebextensions/`).

Make sure your `.ebextensions/` files include:
- `DEBUG=False`
- `SECRET_KEY`: Unique production key
- `ALLOWED_HOSTS`: Your production domain
- `DB_*`: RDS database credentials
- `AWS_*`: S3 credentials for static/media files

---

## Monitoring Deployments

### In GitHub:
1. Go to your repository
2. Click **Actions** tab
3. Click on the workflow run
4. View the logs in real-time

### In AWS:
1. Go to AWS Console → Elastic Beanstalk
2. Select your environment (`nomz-prod`)
3. Check "Environment health" and "Recent activity"

---

## Best Practices

✅ **DO**:
- Test locally before pushing
- Write meaningful commit messages
- Keep `develop` as your main working branch
- Merge small PRs frequently
- Monitor deployment logs

❌ **DON'T**:
- Commit AWS credentials to git
- Push directly to `production` (always go through `develop`)
- Ignore test failures
- Deploy without testing first

---

## Quick Reference

```bash
# Local workflow
git checkout develop
git pull origin develop
# ... make changes, test locally ...
git add .
git commit -m "Description"
git push origin develop

# After testing and approval
git pull origin develop
git push origin develop:production
# or create PR in GitHub and merge

# Check deployment status
# GitHub → Actions → view logs
```

---

## Troubleshooting

| Issue | Solution |
|---|---|
| Tests failing locally but passing in CI | Different environment - check .env file |
| AWS credentials error | Check GitHub Secrets are set correctly |
| Deployment timeout | Increase timeout in deploy.yml |
| Static files not collecting | Add `python manage.py collectstatic --noinput` locally |
| Database migration error | Run `python manage.py migrate` locally and commit changes |

---

## Next Steps

1. ✅ Set up GitHub Secrets (AWS credentials)
2. ✅ Push your code to `develop` branch
3. ✅ Verify tests run automatically
4. ✅ Create a PR to `production` when ready
5. ✅ Monitor the deployment in GitHub Actions
6. ✅ Verify the app is live on AWS EB

Good luck with your deployment! 🚀
