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
    
    # Update setup.py if it exists
    if [ -f "setup.py" ]; then
        sed -i '' "s/version=\"$current_version\"/version=\"$new_version\"/" setup.py
        echo "Updated setup.py version"
        git add setup.py
    fi
    
    # Commit change
    git add DiskMan.py
    git commit -m "Bump version to $new_version"
    current_version=$new_version
fi

# 3. Create Git Tag
echo "Creating git tag v$current_version..."
if git rev-parse "v$current_version" >/dev/null 2>&1; then
    echo "Tag v$current_version already exists. Skipping tag creation."
else
    git tag "v$current_version"
fi

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
# 6. Update Homebrew Tap
TAP_DIR="../homebrew-diskman"

echo "--------------------------------------------------------"
if [ -d "$TAP_DIR" ]; then
    echo "🔄 Found Homebrew Tap at $TAP_DIR. Automating update..."
    
    # Copy local formula to tap (ensures new structure/caveats are synced)
    cp brew/diskman.rb "$TAP_DIR/diskman.rb"
    
    # Update URL and SHA256 in the target file
    # Escape slashes in URL for sed
    escaped_url=$(echo "$tarball_url" | sed 's/\//\\\//g')
    
    # Use sed to replace the specific lines
    sed -i '' "s/url .*/url \"$escaped_url\"/" "$TAP_DIR/diskman.rb"
    sed -i '' "s/sha256 .*/sha256 \"$sha256\"/" "$TAP_DIR/diskman.rb"
    
    echo "Updated diskman.rb with new URL and SHA256."
    
    # Commit and push
    current_dir=$(pwd)
    cd "$TAP_DIR" || exit
    
    echo "Committing and pushing to homebrew-diskman..."
    git add diskman.rb
    git commit -m "Update diskman to v$current_version"
    git push
    
    cd "$current_dir" || exit
    
    echo ""
    echo "✅ Homebrew Tap updated successfully!"
    echo "👉 You can now run: brew upgrade diskman"

else
    echo "⚠️  Could not find ../homebrew-diskman. skipping auto-update."
    echo ""
    echo "🚨  MANUAL UPDATE REQUIRED  🚨"
    echo "--------------------------------------------------------"
    echo "1. Go to your brew repo"
    echo "2. Edit 'diskman.rb'"
    echo "3. Update 'url' to: $tarball_url"
    echo "4. Update 'sha256' to: $sha256"
    echo "5. Commit and push that repo."
    echo ""
    echo "Command to copy SHA to clipboard:"
    echo "echo '$sha256' | pbcopy"
fi
echo "--------------------------------------------------------"
