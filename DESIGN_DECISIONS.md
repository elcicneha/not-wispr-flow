# Design Decisions

Decisions made during development, with context on what was chosen, what was rejected, and why.

---

## Audio Pre-Processing / Compression

**Decision: Don't compress audio before transcription.**

- Considered: `ffmpeg -i audio.mp3 -ac 1 -c:a libopus -b:a 12k -application voip audio.ogg`
- This was suggested to handle the 25 MB file limit on OpenAI's Whisper API
- But we use `faster-whisper` (local inference), which has NO file size limit
- Audio stays in memory as numpy arrays — never touches disk during normal operation
- Adding ffmpeg would mean: write to temp file → spawn subprocess → compress → read back → 200-500ms overhead
- Whisper is compute-bound (model inference), not I/O-bound — smaller files don't help processing speed
- 12kbps Opus is aggressive compression that could hurt transcription accuracy

**Bottom line:** We don't use the OpenAI API, so the 25 MB limit doesn't apply. Compression adds latency without solving the actual bottleneck.

---

## Beam Size

**Decision: Keep beam_size=5 (default).**

- beam_size=1 (greedy): ~3x faster, picks most likely word at each step
- beam_size=5: explores top 5 possibilities, better for unclear audio
- beam_size=3: compromise option
- User prioritizes accuracy over speed ("fast enough, not that slow")
- For clear dictation, beam_size=1 is usually fine, but 5 provides insurance for noisy environments

**Future:** If recordings are always clear speech, could lower to 3 for a speed boost.

---

## Recording Limits: Arbitrary vs. Buffer-to-Disk Overflow

**Decision: No arbitrary limits. Flush buffer to disk when it gets large, and keep recording.**

### What we rejected:

1. **MAX_RECORDING_DURATION (time-based limit)**
   - Originally 10 hours, then lowered to 30 minutes
   - Problem: Arbitrary. Why 30 min and not 45? Different systems can handle different amounts.

2. **MAX_BUFFER_SIZE_MB (size-based limit)**
   - Set to 500 MB
   - Problem: At 32 KB/sec audio, 30 min = 58 MB. The 500 MB limit never triggers before the duration limit. Redundant.

3. **Combined duration + size limits**
   - They were inconsistent — duration hit at 58 MB, size limit at 500 MB. Only one ever mattered.

### Why we rejected both:
- Both are arbitrary guesses about when things "might" go wrong
- Both AUTO-STOP recording when hit, causing the user to lose their transcription flow

### What we chose:
- Buffer-to-disk overflow: when buffer exceeds 10 MB (~5 min), flush to .npy files on disk
- Recording never stops — buffer is cleared after flush, recording continues in memory
- On transcription, overflow files are loaded back in order and concatenated with remaining buffer
- No data loss, no interruption

---

## Flush Strategy: Buffer-Size Threshold

**Decision: Flush when buffer exceeds 10 MB. No RAM monitoring.**

### Options considered:

1. **Always flush every 5 seconds**
   - Pro: Best crash recovery (lose max 5 seconds)
   - Pro: RAM always bounded (~160 KB)
   - Con: Constant SSD writes while recording
   - Rejected because: User concerned about SSD wear from constant writes

2. **Flush only on RAM pressure (psutil)**
   - Pro: Zero disk writes during normal operation
   - Pro: Only writes when system actually needs it
   - Con: If the app crashes before RAM pressure, entire recording is lost
   - Con: A 30-min recording could be lost entirely if crash happens before any flush

3. **Flush when buffer > 200 MB (~1.7 hours)**
   - Pro: Minimal SSD writes
   - Con: Lose up to 1.7 hours of audio on crash — not acceptable

4. **Flush when buffer > 10 MB (~5 min)** ← CHOSEN
   - Size trigger: Crash recovery — lose max ~5 min of audio
   - Short recordings (< 5 min): Zero disk writes (all in memory)
   - SSD impact: Negligible — same total bytes written regardless of flush frequency
   - RAM impact: 10 MB is trivial (0.06% of 16 GB) — no need for RAM monitoring

### Key insight on SSD wear:
Total bytes written to SSD is the same whether you flush in one big write or many small writes. The audio data is the same amount either way. The only "savings" from not flushing is when recordings finish before reaching the threshold — and those stay entirely in memory.

---

## Flush Threshold: 10 MB (~5 min)

**Decision: Start at 10 MB, adjust based on usage data.**

- Most dictation sessions are probably under 1 minute (user's intuition)
- 10 MB = ~5 minutes, so most recordings never trigger a flush (zero SSD writes)
- If a crash happens during a long recording, max loss is ~5 minutes
- Recording analytics (`recording_stats.jsonl`) will track actual usage patterns
- Can adjust threshold up or down based on real data

---

## Recording Analytics

**Decision: Log recording stats to JSONL file for analysis.**

- Each recording logs: timestamp, duration, buffer size, mode (hold/toggle), overflow file count, transcription length
- Format: JSONL (one JSON object per line) — easy to parse with Python/pandas
- Location: `~/Library/Logs/Whispr/recording_stats.jsonl`
- Purpose: Understand actual usage patterns to fine-tune flush threshold
- Zero performance impact: append-only, written after transcription completes

---

## Whisper Model Size

**Decision: Keep "small" model.**

| Model | Size | RAM | Speed | Accuracy |
|-------|------|-----|-------|----------|
| tiny | 40 MB | ~1 GB | Fastest | Lower |
| base | 150 MB | ~1 GB | Fast | Good |
| small | 500 MB | ~2 GB | Moderate | Better |
| medium | 1.5 GB | ~4 GB | Slow | Best |

- "small" balances accuracy and speed well
- User prefers accuracy ("I want accuracy more than fast, but fast enough")
- Can switch to "base" if speed becomes a bigger concern

---

## Dependencies: No psutil

**Decision: Drop psutil. Buffer-size flush alone is sufficient.**

- With a 10 MB buffer threshold, our buffer is trivial (0.06% of 16 GB RAM)
- Flushing 10 MB when system is under memory pressure doesn't help — the pressure comes from other apps
- Buffer-size flush alone handles crash recovery AND keeps RAM bounded
- One fewer dependency to install, bundle, and maintain
- psutil was only needed for `virtual_memory().available` — unnecessary when buffer never grows large
