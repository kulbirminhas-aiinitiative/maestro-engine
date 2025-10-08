# GitHub Token Setup Guide

## 🔑 Interactive Setup (Recommended)

Run this command in your terminal:

```bash
cd /home/ec2-user/projects/maestro-engine
./setup_github_token.sh
```

The script will:
1. Guide you through creating a GitHub token
2. Validate the token
3. Save it to your environment
4. Persist it in `.bashrc` and `.env`

---

## 📋 Manual Setup

### Step 1: Create GitHub Personal Access Token

1. **Go to GitHub Settings:**
   ```
   https://github.com/settings/tokens
   ```

2. **Click:** "Generate new token (classic)"

3. **Configure:**
   - **Note:** `MAESTRO Template Publishing`
   - **Expiration:** 90 days (or custom)
   - **Scopes:** Check ✅ `repo` (full control of private repositories)

4. **Click:** "Generate token"

5. **Copy the token** (starts with `ghp_`)
   - ⚠️ You won't be able to see it again!

---

### Step 2: Set Environment Variable

**Option A: Current Session Only**
```bash
export GITHUB_TOKEN="ghp_your_token_here"
```

**Option B: Persist Across Sessions (Recommended)**
```bash
# Add to ~/.bashrc
echo 'export GITHUB_TOKEN="ghp_your_token_here"' >> ~/.bashrc

# Reload
source ~/.bashrc
```

**Option C: Save to .env File**
```bash
# Add to maestro-engine/.env
echo 'GITHUB_TOKEN=ghp_your_token_here' >> /home/ec2-user/projects/maestro-engine/.env
```

---

### Step 3: Verify Token

```bash
# Test authentication
curl -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/user | jq

# Should return your GitHub user info
```

**Expected output:**
```json
{
  "login": "your-username",
  "id": 12345,
  "name": "Your Name",
  ...
}
```

---

## ✅ Quick Verification Commands

```bash
# Check if token is set
echo $GITHUB_TOKEN

# Test GitHub API access
curl -s -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/user | jq '.login'

# Check token scopes
curl -s -I -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/user | grep X-OAuth-Scopes
```

---

## 🚀 Next Steps After Setup

### 1. Run Dry-Run (Preview)
```bash
cd /home/ec2-user/projects/maestro-engine

poetry run python batch_git_template_publisher_enhanced.py \
  --source-dir /path/to/1000-projects \
  --quality-gate 80 \
  --max-templates 150 \
  --max-per-category 20 \
  --deduplicate \
  --tier-auto-assign \
  --dry-run
```

### 2. Execute Publishing
```bash
nohup poetry run python batch_git_template_publisher_enhanced.py \
  --source-dir /path/to/1000-projects \
  --quality-gate 80 \
  --max-templates 150 \
  --max-per-category 20 \
  --deduplicate \
  --tier-auto-assign \
  --github-token "$GITHUB_TOKEN" \
  --admin-key "maestro-dev-admin-key-67890" \
  --private \
  > batch_publishing.log 2>&1 &

# Monitor
tail -f batch_publishing.log
```

---

## 🔒 Security Best Practices

✅ **DO:**
- Use token expiration (90 days recommended)
- Use minimal scopes (only `repo`)
- Store in environment variables, not in code
- Rotate tokens periodically

❌ **DON'T:**
- Commit tokens to Git
- Share tokens publicly
- Use tokens without expiration
- Grant unnecessary scopes

---

## 🐛 Troubleshooting

### "Bad credentials" Error
```bash
# Check token format (should start with ghp_)
echo $GITHUB_TOKEN | cut -c1-4

# Should output: ghp_
```

### "Not Found" or "404" Errors
```bash
# Check token scopes
curl -I -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/user 2>&1 | grep X-OAuth-Scopes

# Should include: repo
```

### Token Not Persisting
```bash
# Verify it's in .bashrc
grep GITHUB_TOKEN ~/.bashrc

# If not, add it:
echo 'export GITHUB_TOKEN="ghp_your_token"' >> ~/.bashrc
source ~/.bashrc
```

---

## 📝 Alternative: Use GitHub CLI (gh)

If you have `gh` CLI installed:

```bash
# Login with gh
gh auth login

# Get token
gh auth token

# Export to environment
export GITHUB_TOKEN=$(gh auth token)
```

---

## 🔄 Update Token

If you need to update an existing token:

```bash
# Update in .bashrc
sed -i 's|^export GITHUB_TOKEN=.*|export GITHUB_TOKEN="ghp_new_token"|' ~/.bashrc

# Update in .env
sed -i 's|^GITHUB_TOKEN=.*|GITHUB_TOKEN=ghp_new_token|' /home/ec2-user/projects/maestro-engine/.env

# Reload
source ~/.bashrc
```

Or simply run:
```bash
./setup_github_token.sh
```

---

**Ready to publish templates once token is set!**
