## 2024-05-24 - Accessibility issues with emojis in PyQt6 UI
**Learning:** Screen readers often struggle to interpret emojis embedded directly in PyQt6 widget text (like buttons). They may read the emoji name poorly or skip it, making the UI less accessible for visually impaired users.
**Action:** When adding emojis to UI elements like buttons in PyQt6 (e.g. `ModernButton`), always use `setAccessibleName()` to provide a plain text equivalent without the emoji. Additionally, use `setToolTip()` to provide visual context and extra guidance for all users.
