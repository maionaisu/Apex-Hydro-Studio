## 2025-04-28 - PyQt6 Screen Reader Compatibility for Emoji Buttons
**Learning:** PyQt6 buttons (`QPushButton`) with emojis or non-ASCII characters in their text labels can cause screen readers to fail or read unintelligible content. Emojis break screen reader parsing.
**Action:** When creating accessible buttons in PyQt6 that include emojis, use `setAccessibleName()` with a plain text string derived from stripping out non-ASCII characters (`re.sub(r'[^\x00-\x7F]+', '', text).strip()`). Additionally, provide a tooltip via `setToolTip()` to ensure visual context is available for all users.
