# CI/CD Setup Instructions

All configuration files have been created. Follow these steps to complete the setup:

## ✅ Completed Configuration Files

The following files have been created/updated:
- ✅ `.github/workflows/ci.yml` - GitHub Actions workflow
- ✅ `pytest.ini` - Test configuration
- ✅ `.flake8` - Linting rules
- ✅ `.gitignore` - Updated with test artifacts
- ✅ `README.md` - Added CI/CD badges

## 📋 Steps You Need to Complete

### 1. Setup Codecov (5 minutes)

Codecov provides code coverage reports and PR comments.

**Steps:**

1. **Sign up at Codecov:**
   - Go to https://codecov.io
   - Click "Sign up with GitHub"
   - Authorize Codecov to access your repositories

2. **Add your repository:**
   - Once logged in, you'll see your repositories
   - Find `pdf-converter-web-app` in the list
   - If not visible, click "Add new repository" and select it

3. **Get your upload token:**
   - Click on your repository in Codecov dashboard
   - Go to **Settings** → **General**
   - Copy the **CODECOV_TOKEN** (it looks like: `a1b2c3d4-e5f6-7890-abcd-ef1234567890`)

4. **Add token to GitHub Secrets:**
   - Go to your GitHub repository: https://github.com/aditya-kamatt/pdf-converter-web-app
   - Click **Settings** → **Secrets and variables** → **Actions**
   - Click **New repository secret**
   - Name: `CODECOV_TOKEN`
   - Value: (paste the token from Codecov)
   - Click **Add secret**

### 2. Configure GitHub Branch Protection (3 minutes)

Protect the `main` branch to require passing tests before merging.

**Steps:**

1. **Go to branch protection settings:**
   - Navigate to: https://github.com/aditya-kamatt/pdf-converter-web-app/settings/branches
   - Click **Add branch protection rule**

2. **Configure the rule:**
   - **Branch name pattern:** `main`
   
   - ✅ **Require a pull request before merging**
     - (No need to select "Require approvals" since it's a solo project)
   
   - ✅ **Require status checks to pass before merging**
     - ✅ Check "Require branches to be up to date before merging"
     - In the search box, type `test` and select it (this will appear after your first CI run)
   
   - ✅ **Require conversation resolution before merging**
   
   - ✅ **Do not allow bypassing the above settings**
   
   - (Optional) ✅ **Require linear history** - keeps git history clean

3. **Click "Create" or "Save changes"**

**Note:** The `test` status check won't appear in the list until you run the workflow at least once. You can add it after step 3.

### 3. Commit and Push Configuration Files (2 minutes)

Commit all the new configuration files to your `dev` branch:

```bash
# Make sure you're on dev branch
git checkout dev

# Stage all new configuration files
git add .github/workflows/ci.yml
git add pytest.ini
git add .flake8
git add .gitignore
git add README.md

# Commit the changes
git commit -m "Add CI/CD pipeline with GitHub Actions and Codecov"

# Push to remote
git push origin dev
```

### 4. Test the CI/CD Pipeline (10 minutes)

Create a test PR to verify everything works:

#### 4.1 Create a Pull Request

**Option A: Via GitHub Web Interface**
1. Go to: https://github.com/aditya-kamatt/pdf-converter-web-app
2. Click "Pull requests" tab
3. Click "New pull request"
4. Base: `main` ← Compare: `dev`
5. Click "Create pull request"
6. Add title: "Setup CI/CD pipeline"
7. Click "Create pull request"

**Option B: Via Command Line (with GitHub CLI)**
```bash
gh pr create --base main --head dev --title "Setup CI/CD pipeline" --body "Adds automated testing and coverage reporting"
```

#### 4.2 Watch the CI Run

1. Go to the **Actions** tab in your repository
2. You should see a workflow run starting (it will take 2-3 minutes)
3. Click on it to watch the progress

**Expected behavior:**
- ✅ Python environment sets up
- ✅ Dependencies install
- ✅ Code quality checks run
- ✅ Tests execute successfully
- ✅ Coverage report uploads to Codecov
- ✅ Bot comments on your PR with results

#### 4.3 Check Coverage Report

1. Go to https://codecov.io/gh/aditya-kamatt/pdf-converter-web-app
2. You should see your first coverage report
3. Explore which lines are covered/not covered

#### 4.4 Merge the PR

Once tests pass:
1. Review the PR (check the green checkmark)
2. Click "Merge pull request"
3. Confirm the merge

#### 4.5 Verify Railway Deployment

After merging to `main`:
1. Go to your Railway dashboard
2. You should see a new deployment starting automatically
3. Wait 3-5 minutes for deployment to complete
4. Visit your app URL to verify it works

## 🎯 Success Criteria

You'll know everything is working when:
- ✅ PR shows green checkmark with "All checks have passed"
- ✅ Bot leaves a comment on your PR
- ✅ Codecov shows coverage report
- ✅ You can see coverage badge in README
- ✅ After merge, Railway deploys automatically
- ✅ App is accessible and `/health` endpoint works

## 🔍 Troubleshooting

### CI workflow doesn't start
- Check that `.github/workflows/ci.yml` was pushed to GitHub
- Verify the workflow file has no YAML syntax errors
- Check Actions tab → Make sure Actions are enabled

### Codecov upload fails
- Verify `CODECOV_TOKEN` is correctly set in GitHub Secrets
- Check that the secret name is exactly `CODECOV_TOKEN` (case-sensitive)
- Try re-generating the token in Codecov

### Tests fail
- Run tests locally first: `pytest tests/ -v`
- Check the error message in the Actions log
- Common issues:
  - Missing system dependencies (ImageMagick)
  - Import errors (missing packages)
  - Golden test mismatches

### Railway doesn't deploy
- Verify Railway is connected to your GitHub repository
- Check that `main` is set as the production branch in Railway
- Look at Railway deployment logs for errors

## 📚 Additional Resources

- **GitHub Actions Docs:** https://docs.github.com/en/actions
- **Codecov Docs:** https://docs.codecov.com/docs
- **Railway Docs:** https://docs.railway.app/
- **pytest Docs:** https://docs.pytest.org/

## 🚀 Next Steps (Optional)

Once everything is working, you can:
1. Add more tests to increase coverage
2. Set up pre-commit hooks for local linting
3. Add performance benchmarks
4. Create a staging environment
5. Add automated dependency updates (Dependabot)

## 📞 Need Help?

If you run into issues:
1. Check the workflow logs in the Actions tab
2. Review the error messages in PR comments
3. Verify all secrets are correctly configured
4. Make sure Railway integration is active

