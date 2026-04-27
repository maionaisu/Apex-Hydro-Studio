## 2026-04-27 - [Emoji Accessibility in PyQt6]
**Learning:** Screen readers often struggle to interpret emojis embedded within text (e.g., buttons in PyQt6 UIs like "💾 Simpan"). This creates an accessibility barrier for users relying on assistive technologies.
**Action:** Always add `setAccessibleName()` with a plain text equivalent to UI elements (like `QPushButton`) that contain emojis or icon-like characters. This ensures clear and accurate reading by screen readers.
