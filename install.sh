#!/bin/bash

# DiskMan V3 Installation Script
# Sets up a virtual environment and installs dependencies safely.

set -e  # Exit on error

INSTALL_DIR="$HOME/.diskman"
VENV_DIR="$INSTALL_DIR/venv"
BIN_NAME="diskman"
LINK_PATH="/usr/local/bin/$BIN_NAME"

echo "💿 Installing DiskMan V3..."

# 1. Ensure we are in the correct directory (if cloned manually) or setup dir
if [ -d "$INSTALL_DIR" ]; then
    cd "$INSTALL_DIR"
else
    echo "❌ Error: Installation directory $INSTALL_DIR not found."
    echo "   Please clone the repository first: git clone https://github.com/mrsamseen/DiskMan.git $INSTALL_DIR"
    exit 1
fi

# 2. Create Virtual Environment
if [ ! -d "$VENV_DIR" ]; then
    echo "📦 Creating Python virtual environment..."
    python3 -m venv "$VENV_DIR"
else
    echo "📦 Virtual environment already exists."
fi

# 3. Install Dependencies
echo "⬇️  Installing dependencies..."
"$VENV_DIR/bin/pip" install --upgrade pip > /dev/null
"$VENV_DIR/bin/pip" install -r requirements.txt

# 4. Make main script executable
chmod +x DiskMan.py

# 5. Create Launcher Script
LAUNCHER="$INSTALL_DIR/diskman_launcher.sh"
echo "#!/bin/bash" > "$LAUNCHER"
echo "source \"$VENV_DIR/bin/activate\"" >> "$LAUNCHER"
echo "exec python3 \"$INSTALL_DIR/DiskMan.py\" \"\$@\"" >> "$LAUNCHER"
chmod +x "$LAUNCHER"

# 6. Symlink to /usr/local/bin
echo "🔗 Creating symlink (requires sudo)..."
if [ -L "$LINK_PATH" ] || [ -f "$LINK_PATH" ]; then
    sudo rm "$LINK_PATH"
fi
sudo ln -s "$LAUNCHER" "$LINK_PATH"

echo ""
echo "✅ Installation Complete!"
echo "   Run 'diskman' to start."
