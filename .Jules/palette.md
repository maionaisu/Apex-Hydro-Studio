## 2026-05-26 - [Accessibility: setBuddy and Emoji Stripping]
**Learning:** In PyQt6, composite form controls using QFormLayout.addRow with pre-existing QLabels do not auto-set the buddy, requiring explicit QLabel.setBuddy(input_widget). Also, screen readers struggle with emojis; since the emoji library isn't available, we strip them for setAccessibleName() using precise regex blocks.
**Action:** Always explicitly set buddies for custom form rows, and strip emojis for ARIA-like labels without removing the visual text.
