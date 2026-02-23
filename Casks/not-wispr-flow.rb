cask "not-wispr-flow" do
  version "1.0.0"  # UPDATE THIS with each release
  sha256 "PUT_SHA256_HERE"  # UPDATE THIS with each release (GitHub Actions will provide this)

  url "https://github.com/elcicneha/not-wispr-flow/releases/download/v#{version}/NotWisprFlow-v#{version}.dmg"
  name "Not Wispr Flow"
  desc "Free, offline voice-to-text for macOS"
  homepage "https://github.com/elcicneha/not-wispr-flow"

  # Requires Apple Silicon
  depends_on macos: ">= :big_sur"
  depends_on arch: :arm64

  # System dependency
  depends_on formula: "portaudio"

  app "Not Wispr Flow.app"

  # Inform user about permissions needed
  postflight do
    system_command "/usr/bin/osascript",
                   args: ["-e", 'display notification "Please grant Microphone, Accessibility, and Input Monitoring permissions in System Settings" with title "Not Wispr Flow Installed"']
  end

  uninstall quit: "com.notwisprflow.app"

  zap trash: [
    "~/Library/Logs/NotWisprFlow",
  ]

  caveats <<~EOS
    Not Wispr Flow requires the following permissions:
    1. System Settings → Privacy & Security → Microphone
    2. System Settings → Privacy & Security → Accessibility
    3. System Settings → Privacy & Security → Input Monitoring

    On first launch, right-click the app and select "Open" to bypass Gatekeeper.

    Usage:
    - Hold mode: Hold Control → speak → release
    - Toggle mode: Press Control + Space → speak → press Control
  EOS
end
