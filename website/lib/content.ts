export const REPO_URL = "https://github.com/elcicneha/not-wispr-flow";
export const DOWNLOAD_ZIP_URL = `${REPO_URL}/archive/refs/heads/main.zip`;

export const features = [
  {
    symbol: "*",
    title: "Offline by default.",
    body: "Whisper runs on Apple Silicon's GPU via MLX. Nothing leaves your Mac.",
  },
  {
    symbol: "→",
    title: "Cloud-fast when you want.",
    body: "Optional Groq key for sub-second cloud transcription.",
  },
  {
    symbol: "[]",
    title: "Smart fallback.",
    body: "Online when it can. Offline when your wifi blinks. Auto-detects.",
  },
  {
    symbol: "✱",
    title: "AI text cleanup.",
    body: "Plug in Gemini, GPT, Claude, or Groq Llama to polish what you said.",
  },
  {
    symbol: "§",
    title: "System-wide.",
    body: "Works in any text field — Slack, terminal, Notion, code editor. Wherever your cursor is.",
  },
  {
    symbol: "¶",
    title: "Yours to tweak.",
    body: "Custom vocabulary, hotkeys, models, prompts. It's just Python in your home folder.",
  },
] as const;

export const installSteps = [
  {
    num: "01",
    title: "Download.",
    body: "Hit the button. You'll get a ZIP from the GitHub repo.",
  },
  {
    num: "02",
    title: "Run the installer.",
    body: "Right-click the unzipped folder → New Terminal at Folder, then paste:",
    code: "./install.sh",
    note: "Asks for your Mac password once (creates a local code-signing cert). Takes 5–10 minutes the first time.",
  },
  {
    num: "03",
    title: "Grant permissions.",
    body: "Open Not Wispr Flow from Spotlight. In System Settings, give it access to:",
    permissions: ["Microphone", "Accessibility", "Input Monitoring"],
    note: "You only need to do this once.",
  },
] as const;

export const marqueeItems = [
  "draft an email",
  "write a prompt",
  "dictate a slack message",
  "compose a tweet",
  "take a note",
  "dictate a doc",
  "reply to a dm",
  "write a commit message",
  "jot an idea",
];
