## 2024-05-14 - Ensure Buddy Linking for PyQt6 Forms
**Learning:** In PyQt6, `QFormLayout.addRow("String", widget)` automatically creates a label and sets the buddy. However, in custom layouts or classes like `FormRow` where `QLabel` is explicitly initialized, the buddy is NOT auto-set. This prevents screen readers from associating the label with the input field, hurting form accessibility.
**Action:** When manually creating a composite form row linking a `QLabel` with an input widget, always explicitly call `label.setBuddy(input_widget)` to ensure keyboard focus flow and screen reader associations.

## 2024-05-14 - Screen Reader Compatibility with Emojis in Buttons
**Learning:** Screen readers struggle to correctly articulate button labels that include complex emojis, often reading out unhelpful literal descriptions or getting stuck. Simply using ASCII exclusion `[^\x00-\x7F]` strips away international/accented text which degrades accessibility in other languages.
**Action:** Strip emojis specifically for PyQt6 `setAccessibleName()` by targeting Unicode ranges typically reserved for emojis and symbols (e.g., `[\U00010000-\U0010ffff\u25A0-\u25FF\u2700-\u27BF\u2600-\u26FF\u2B00-\u2BFF\u2300-\u23FF\uFE0F]`), preserving both the visual representation with emojis via `setText` and an accurate vocalization text for screen readers.
