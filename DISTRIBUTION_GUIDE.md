# Distribution Setup Guide

This guide will help you set up automated builds and easy installation for users.

## What We're Setting Up

1. **GitHub Actions** - Automatically builds your app when you create a release
2. **DMG Files** - Pretty installer files users can download
3. **Homebrew Cask** - One-command installation for users

After setup, users can install with just:
```bash
brew tap elcicneha/tap
brew install --cask not-wispr-flow
```

---

## Part 1: Test DMG Creation Locally (5 minutes)

Let's make sure the DMG creation works on your computer first.

### Step 1: Build your app
```bash
cd ~/Documents/Codes/not-wispr-flow
./scripts/install_service.sh
```

Wait for it to finish. This creates `dist/Not Wispr Flow.app`

### Step 2: Create a DMG
```bash
./scripts/create_dmg.sh 1.0.0
```

This creates `dist/NotWisprFlow-1.0.0.dmg`

### Step 3: Test the DMG
1. Open Finder and go to the `dist` folder
2. Double-click `NotWisprFlow-1.0.0.dmg`
3. A window opens showing the app and Applications folder
4. Try dragging the app to Applications
5. Try opening it (remember to right-click → Open)

**If this works, move to Part 2. If not, let me know what error you see.**

---

## Part 2: Set Up GitHub Actions (10 minutes)

GitHub Actions is like a robot that builds your app automatically whenever you make a release.

### Step 1: Push the new files to GitHub

```bash
cd ~/Documents/Codes/not-wispr-flow
git add .github/workflows/release.yml
git add scripts/create_dmg.sh
git add Casks/not-wispr-flow.rb
git add DISTRIBUTION_GUIDE.md
git commit -m "Add automated build and distribution setup"
git push
```

### Step 2: Enable GitHub Actions

1. Go to your GitHub repository: https://github.com/elcicneha/not-wispr-flow
2. Click the **"Actions"** tab at the top
3. If you see a green button saying "I understand my workflows, go ahead and enable them", click it

That's it! GitHub Actions is now enabled.

---

## Part 3: Create Your First Release (15 minutes)

Now let's create a release. This will trigger GitHub Actions to automatically build everything.

### Step 1: Create a release on GitHub

1. Go to: https://github.com/elcicneha/not-wispr-flow/releases
2. Click **"Create a new release"** (or "Draft a new release")
3. Click **"Choose a tag"** and type: `v1.0.0` (then click "Create new tag: v1.0.0")
4. **Release title**: Type `v1.0.0`
5. **Description**: Write something like:
   ```
   First release of Not Wispr Flow!

   Features:
   - Offline voice-to-text for macOS
   - Hold Control to dictate
   - Toggle mode with Control + Space

   Installation:
   Download the DMG below or use Homebrew (see README)
   ```
6. Click **"Publish release"**

### Step 2: Watch GitHub Actions Build

1. Go to: https://github.com/elcicneha/not-wispr-flow/actions
2. You'll see a workflow running called "Build and Release"
3. Click on it to watch the progress
4. Wait about 10-15 minutes for it to finish

**What it's doing:**
- Setting up a Mac computer
- Installing Python and dependencies
- Building your app
- Creating a DMG
- Uploading the DMG to your release

### Step 3: Check the Release

1. Go back to: https://github.com/elcicneha/not-wispr-flow/releases
2. Click on your `v1.0.0` release
3. Scroll down to **"Assets"**
4. You should see: `NotWisprFlow-v1.0.0.dmg`
5. There should also be a comment with a SHA256 hash (a long string of letters/numbers)

**If you see the DMG file, congrats! The automation works!**

---

## Part 4: Set Up Homebrew Tap (10 minutes)

A "tap" is Homebrew's term for a repository of installation recipes.

### Step 1: Create a tap repository

1. Go to GitHub: https://github.com/new
2. Repository name: `homebrew-tap` (must be exactly this name)
3. Description: "Homebrew tap for Not Wispr Flow"
4. Make it **Public**
5. **Don't** check any boxes (no README, no .gitignore)
6. Click **"Create repository"**

### Step 2: Copy the repository URL

After creating it, you'll see instructions. Copy the URL that looks like:
```
https://github.com/elcicneha/homebrew-tap.git
```

### Step 3: Push your cask formula

```bash
cd ~
git clone https://github.com/elcicneha/homebrew-tap.git
cd homebrew-tap

# Copy the cask file
mkdir -p Casks
cp ~/Documents/Codes/not-wispr-flow/Casks/not-wispr-flow.rb Casks/

git add Casks/not-wispr-flow.rb
git commit -m "Add not-wispr-flow cask"
git push
```

### Step 4: Update the cask with the real SHA256

Remember that SHA256 hash from the release comment? We need to put it in the cask file.

1. Go to your release: https://github.com/elcicneha/not-wispr-flow/releases/tag/v1.0.0
2. Copy the SHA256 hash from the comment (it's a long string like `a3b4c5d6e7f8...`)
3. Edit the cask file:

```bash
cd ~/homebrew-tap
nano Casks/not-wispr-flow.rb
```

4. Replace `PUT_SHA256_HERE` with the actual hash
5. Make sure the version says `1.0.0`
6. Press `Ctrl+O` to save, `Enter` to confirm, `Ctrl+X` to exit
7. Push the change:

```bash
git add Casks/not-wispr-flow.rb
git commit -m "Update SHA256 hash for v1.0.0"
git push
```

---

## Part 5: Test Installation (5 minutes)

Let's test if users can actually install it!

### Test Homebrew installation:

```bash
# Add your tap
brew tap elcicneha/tap

# Install the app
brew install --cask not-wispr-flow
```

This should download the DMG, extract it, and install the app to `/Applications`!

### Test DMG download:

1. Go to your release page: https://github.com/elcicneha/not-wispr-flow/releases
2. Download `NotWisprFlow-v1.0.0.dmg`
3. Open it and test installation

---

## Part 6: Update Your README (5 minutes)

Now update your main README with the easy installation instructions.

Replace the long setup section with:

```markdown
## Installation

### Option 1: Homebrew (Recommended)

```bash
brew tap elcicneha/tap
brew install --cask not-wispr-flow
```

### Option 2: Download DMG

1. Download the latest release: [Releases page](https://github.com/elcicneha/not-wispr-flow/releases)
2. Open the DMG
3. Drag "Not Wispr Flow" to Applications
4. Right-click the app and select "Open" (first time only)

### First Launch

Grant permissions in System Settings → Privacy & Security:
- Microphone
- Accessibility
- Input Monitoring
```

---

## For Future Releases

When you want to release a new version:

1. Make your code changes
2. Commit and push to GitHub
3. Create a new release (e.g., `v1.0.1`)
4. Wait for GitHub Actions to build
5. Get the SHA256 from the release comment
6. Update `homebrew-tap/Casks/not-wispr-flow.rb`:
   - Change version number
   - Update SHA256
   - Commit and push

Users can then update with:
```bash
brew upgrade not-wispr-flow
```

---

## Troubleshooting

### GitHub Actions failed
- Click on the failed job to see error details
- Common issues: certificate creation, missing dependencies
- You can manually trigger it: Actions tab → Build and Release → Run workflow

### Homebrew installation fails
- Check the SHA256 is correct
- Make sure the DMG URL is accessible
- Try: `brew uninstall --cask not-wispr-flow` then reinstall

### DMG creation fails locally
- Make sure `dist/Not Wispr Flow.app` exists
- Check you have enough disk space (need ~2GB free)
- Try: `rm -rf dist` then rebuild

---

## Summary

**What users do now:**
```bash
brew tap elcicneha/tap
brew install --cask not-wispr-flow
```

**Or download DMG from releases page**

That's it! From 15+ steps down to 2 commands or 1 download.

**What you do for new releases:**
1. Create GitHub release
2. Wait for build
3. Update homebrew-tap with new SHA256

Questions? Open an issue on GitHub!
