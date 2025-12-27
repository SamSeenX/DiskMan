#!/bin/bash

# DiskMan Release Helper
# This script automates version bumping, tagging, and Homebrew tap updates

set -e  # Exit on error

echo "🚀 Starting DiskMan Release Process..."
echo ""

# 1. Get current version - more robust extraction
current_version=$(grep -m1 '__version__' DiskMan.py | sed 's/.*"\([^"]*\)".*/\1/')
echo "Current version: $current_version"

# 2. Ask for new version
read -p "Enter new version (or press Enter to keep $current_version): " new_version

if [ -n "$new_version" ] && [ "$new_version" != "$current_version" ]; then
    echo ""
    echo "Updating version to $new_version..."
    
    # Update DiskMan.py - use exact pattern matching
    sed -i '' 's/__version__ = "'$current_version'"/__version__ = "'$new_version'"/' DiskMan.py
    
    # Verify the update worked
    updated_version=$(grep -m1 '__version__' DiskMan.py | sed 's/.*"\([^"]*\)".*/\1/')
    if [ "$updated_version" != "$new_version" ]; then
        echo "❌ ERROR: Failed to update DiskMan.py"
        exit 1
    fi
    echo "  ✓ Updated DiskMan.py"
    
    # Update setup.py
    if [ -f "setup.py" ]; then
        sed -i '' 's/version="'$current_version'"/version="'$new_version'"/' setup.py
        echo "  ✓ Updated setup.py"
    fi
    
    # Commit changes
    git add DiskMan.py setup.py
    git commit -m "Bump version to $new_version"
    echo "  ✓ Committed changes"
    
    current_version=$new_version
fi

echo ""

# 3. Create Git Tag
echo "Creating git tag v$current_version..."
if git rev-parse "v$current_version" >/dev/null 2>&1; then
    echo "  Tag already exists. Force updating..."
    git tag -f "v$current_version"
else
    git tag "v$current_version"
fi

# 4. Push to GitHub
echo "Pushing to GitHub..."
git push origin main
git push -f origin "v$current_version"
echo "  ✓ Pushed to GitHub"

# 5. Calculate SHA256
echo ""
echo "--------------------------------------------------------"
echo "⏳ Waiting for GitHub to register the tag..."
sleep 3

tarball_url="https://github.com/SamSeenX/DiskMan/archive/refs/tags/v$current_version.tar.gz"
echo "Downloading: $tarball_url"
sha256=$(curl -sL "$tarball_url" | shasum -a 256 | awk '{print $1}')

echo ""
echo "✅ Release v$current_version published!"
echo "🔗 URL: $tarball_url"
echo "🔑 SHA256: $sha256"
echo "--------------------------------------------------------"

# 6. Update Homebrew Tap
TAP_DIR="../homebrew-apps"

if [ -d "$TAP_DIR" ]; then
    echo ""
    echo "🔄 Updating Homebrew Tap..."
    
    # Pull latest
    (cd "$TAP_DIR" && git pull)
    
    # Ensure Formula directory exists
    mkdir -p "$TAP_DIR/Formula"
    
    # Copy formula template
    cp brew/diskman.rb "$TAP_DIR/Formula/diskman.rb"
    
    # Update URL and SHA256 using escaped patterns
    escaped_url=$(echo "$tarball_url" | sed 's/[\/&]/\\&/g')
    sed -i '' "s|url \".*\"|url \"$tarball_url\"|g" "$TAP_DIR/Formula/diskman.rb"
    sed -i '' "s|sha256 \".*\"|sha256 \"$sha256\"|g" "$TAP_DIR/Formula/diskman.rb"
    
    echo "  ✓ Updated Formula/diskman.rb"
    
    # Commit and push
    (cd "$TAP_DIR" && git add Formula/diskman.rb && git commit -m "Update diskman to v$current_version" && git push)
    
    echo ""
    echo "✅ Homebrew Tap updated successfully!"
    echo "👉 Users can now run: brew update && brew upgrade diskman"
else
    echo ""
    echo "⚠️  Could not find $TAP_DIR. Skipping Homebrew update."
    echo ""
    echo "🚨 MANUAL UPDATE REQUIRED 🚨"
    echo "1. Update 'url' to: $tarball_url"
    echo "2. Update 'sha256' to: $sha256"
    echo ""
    echo "Copy SHA to clipboard: echo '$sha256' | pbcopy"
fi

echo "--------------------------------------------------------"
echo "🎉 Release complete!"
echo "--------------------------------------------------------"
