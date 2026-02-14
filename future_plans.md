# Future Plans

## Hinglish/Romanization Support

### Problem
Currently, when speaking in Hindi (or other non-English languages), Whisper translates the speech to English instead of transcribing it in romanized form (Hinglish).

### Desired Behavior
- If speaking in Hindi, transcribe the Hindi words phonetically in English/Latin script (Hinglish)
- Example: Speaking "मैं जा रहा हूं" should output "main ja raha hoon" not "I am going"

### Implementation Approach
1. Remove `language="en"` constraint from Whisper transcription
2. Let Whisper transcribe in the original language
3. Add transliteration/romanization step:
   - Detect if output is in non-Latin script (Devanagari, etc.)
   - Use transliteration library (e.g., `indic-transliteration` or similar) to convert to romanized text
4. Return romanized output instead of native script

### Required Dependencies
- `indic-transliteration` or similar romanization library
- Language detection (could use Whisper's language detection info)

### Notes
- This would preserve the original language while making it readable/typeable in English characters
- Useful for code-switching between Hindi and English
