#!/bin/bash

# DiskMan Release Helper
# This script automates tagging and reminds you to update Homebrew

echo "🚀 Starting DiskMan Release Process..."

# 1. Get current version
current_version=$(grep "__version__" DiskMan.py | cut -d '"' -f 2)
echo "Current version in DiskMan.py: $current_version"

# 2. Ask for new version
read -p "Enter new version (or press Enter to keep $current_version): " new_version
if [ ! -z "$new_version" ] && [ "$new_version" != "$current_version" ]; then
    echo "Updating version to $new_version..."
    # Update Python file
    sed -i '' "s/__version__ = \"$current_version\"/__version__ = \"$new_version\"/" DiskMan.py
    
    # Commit change
    git add DiskMan.py
    git commit -m "Bump version to $new_version"
    current_version=$new_version
fi

# 3. Create Git Tag
echo "Creating git tag v$current_version..."
git tag "v$current_version"

# 4. Push
echo "Pushing to GitHub..."
git push origin main
git push origin "v$current_version"

# 5. Calculate SHA256 (Downloading from GitHub)
echo "--------------------------------------------------------"
echo "⏳ Waiting for GitHub to register the tag..."
sleep 2

tarball_url="https://github.com/MrSamSeen/DiskMan/archive/refs/tags/v$current_version.tar.gz"
echo "Downloading source for SHA calculation: $tarball_url"
sha256=$(curl -sL "$tarball_url" | shasum -a 256 | awk '{print $1}')

echo ""
echo "✅ Release v$current_version published!"
echo "🔗 URL: $tarball_url"
echo "🔑 SHA256: $sha256"
echo ""
echo "--------------------------------------------------------"
echo "🚨  HOMEBREW UPDATE REMINDER  🚨"
echo "--------------------------------------------------------"
echo "You MUST now update your Homebrew Tap repository."
echo ""
echo "1. Go to your brew repo (e.g., ../homebrew-diskman)"
echo "2. Edit 'diskman.rb'"
echo "3. Update 'url' to: $tarball_url"
echo "4. Update 'sha256' to: $sha256"
echo "5. Commit and push that repo."
echo ""
echo "Command to copy SHA to clipboard:"
echo "echo '$sha256' | pbcopy"
echo "--------------------------------------------------------"
