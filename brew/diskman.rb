class Diskman < Formula
  include Language::Python::Virtualenv

  desc "DiskMan V3 - Enhanced Disk Space Analyzer"
  homepage "https://github.com/MrSamSeen/DiskMan"
  url "URL_PLACEHOLDER"
  sha256 "SHA_PLACEHOLDER"
  license "MIT"

  depends_on "python@3.11"

  # Dependencies
  resource "colorama" do
    url "https://files.pythonhosted.org/packages/d1/d6/3965ed04c63042e047cb6a3e6ed1a63a35087b6a609aa3a15ed8ac56c221/colorama-0.4.6.tar.gz"
    sha256 "08695f5cb7ed6e0531a20572697297273c47b8cae5a63ffc6d6ed5c201be6e44"
  end

  resource "humanize" do
    url "https://files.pythonhosted.org/packages/f7/6d/4b2e8e9e8f6e6c4e0e6e8e8e8e8e8e8e8e8e/humanize-4.9.0.tar.gz"
    sha256 "7cae51a82f3c7ae05c0883b2df7e7049830573934d402f1ba8736fb1c496bc4a"
  end

  resource "send2trash" do
    url "https://files.pythonhosted.org/packages/49/74/59dd8b0a99ded62d3a95c9b68d4d84a7e94c9693eb46b3f790eb3e17ae13/Send2Trash-1.8.2.tar.gz"
    sha256 "c132d59fa44b9ca2b1699af918e730d30053b6b7d5248100b561b8f1797d19ba"
  end

  def install
    virtualenv_install_with_resources
  end

  test do
    system "#{bin}/diskman", "--help"
  end
end
