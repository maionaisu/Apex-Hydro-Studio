## 2024-05-14 - [A11y] FormRow & ModernButton Enhancements
**Learning:** PyQt6 `QFormLayout.addRow()` combined with `QLabel` does not automatically associate the label with the input for screen readers (unlike when passing a simple string). Additionally, screen readers stumble on buttons that use emojis as visual markers.
**Action:** When building custom composite form rows (e.g. `FormRow`), explicitly map `lbl.setBuddy(input_widget)`. When instantiating text on buttons containing visual emojis, use targeted unicode regex matching to strip emojis and apply `setAccessibleName(clean_text)`.
