## 2024-04-23 - Emojis in Accessible Names
**Learning:** Screen readers often struggle to interpret emojis correctly when they are used in buttons or text.
**Action:** When adding emojis to UI elements like buttons (e.g., "▶ RUN ENGINE" or "⏹ ABORT FORCE KILL"), always set `setAccessibleName()` with plain text so screen readers can properly read the button's action.
