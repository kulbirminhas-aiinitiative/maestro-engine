#!/bin/bash
###############################################################################
# GitHub Token Setup - Interactive
# Sets up GitHub personal access token for template publishing
###############################################################################

set -e

echo "============================================================================"
echo "  🔑 GitHub Token Setup for Template Publishing"
echo "============================================================================"
echo ""

# Check if token already exists
if [ -n "$GITHUB_TOKEN" ]; then
    echo "✅ GitHub token already set in environment"
    echo "   Current token: ${GITHUB_TOKEN:0:7}...${GITHUB_TOKEN: -4}"
    echo ""
    read -p "Do you want to update it? (y/n): " UPDATE
    if [ "$UPDATE" != "y" ]; then
        echo "Keeping existing token."
        exit 0
    fi
fi

echo "📋 To create a GitHub Personal Access Token:"
echo ""
echo "1. Go to: https://github.com/settings/tokens"
echo "2. Click: 'Generate new token (classic)'"
echo "3. Set:"
echo "   - Note: 'MAESTRO Template Publishing'"
echo "   - Expiration: 90 days (or custom)"
echo "   - Scopes: Check 'repo' (full control of private repositories)"
echo "4. Click: 'Generate token'"
echo "5. Copy the token (starts with 'ghp_')"
echo ""
echo "⚠️  Important: You won't be able to see it again after leaving the page!"
echo ""

# Prompt for token
read -sp "Paste your GitHub token here: " GITHUB_TOKEN
echo ""
echo ""

# Validate token format
if [[ ! "$GITHUB_TOKEN" =~ ^ghp_[a-zA-Z0-9]{36}$ ]]; then
    echo "⚠️  Warning: Token format looks unusual (expected: ghp_xxxxx...)"
    read -p "Continue anyway? (y/n): " CONTINUE
    if [ "$CONTINUE" != "y" ]; then
        echo "Setup cancelled."
        exit 1
    fi
fi

# Test token
echo "🔍 Testing GitHub token..."
RESPONSE=$(curl -s -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/user)

if echo "$RESPONSE" | grep -q '"login"'; then
    USERNAME=$(echo "$RESPONSE" | grep -o '"login": "[^"]*' | cut -d'"' -f4)
    echo "✅ Token is valid!"
    echo "   Authenticated as: $USERNAME"
    echo ""
else
    echo "❌ Token validation failed!"
    echo "   Response: $RESPONSE"
    exit 1
fi

# Save to environment
export GITHUB_TOKEN="$GITHUB_TOKEN"

# Save to .bashrc for persistence
if ! grep -q "export GITHUB_TOKEN=" ~/.bashrc; then
    echo "" >> ~/.bashrc
    echo "# GitHub token for MAESTRO template publishing" >> ~/.bashrc
    echo "export GITHUB_TOKEN=\"$GITHUB_TOKEN\"" >> ~/.bashrc
    echo "✅ Token saved to ~/.bashrc (will persist across sessions)"
else
    # Update existing entry
    sed -i "s|^export GITHUB_TOKEN=.*|export GITHUB_TOKEN=\"$GITHUB_TOKEN\"|" ~/.bashrc
    echo "✅ Token updated in ~/.bashrc"
fi

# Save to .env file for maestro-engine
ENV_FILE="/home/ec2-user/projects/maestro-engine/.env"
if [ -f "$ENV_FILE" ]; then
    if grep -q "^GITHUB_TOKEN=" "$ENV_FILE"; then
        sed -i "s|^GITHUB_TOKEN=.*|GITHUB_TOKEN=$GITHUB_TOKEN|" "$ENV_FILE"
    else
        echo "GITHUB_TOKEN=$GITHUB_TOKEN" >> "$ENV_FILE"
    fi
    echo "✅ Token saved to $ENV_FILE"
fi

echo ""
echo "============================================================================"
echo "  ✅ GitHub Token Setup Complete!"
echo "============================================================================"
echo ""
echo "Token is now available as: \$GITHUB_TOKEN"
echo ""
echo "Test it:"
echo "  curl -H \"Authorization: token \$GITHUB_TOKEN\" https://api.github.com/user | jq"
echo ""
echo "Next steps:"
echo "  1. Run dry-run to preview template publishing:"
echo "     cd /home/ec2-user/projects/maestro-engine"
echo "     poetry run python batch_git_template_publisher_enhanced.py --dry-run --quality-gate 80"
echo ""
echo "  2. Execute actual publishing when ready (see QUICK_START_1000_TEMPLATES.md)"
echo ""
