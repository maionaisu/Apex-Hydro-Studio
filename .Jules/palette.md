## YYYY-MM-DD - [Title]\n**Learning:** [UX/a11y insight]\n**Action:** [How to apply next time]
## 2026-05-27 - [A11y/UX improvements in FormRow and ModernButton]
**Learning:** PyQt6 `QFormLayout.addRow` doesn't automatically link labels and inputs when passed pre-existing QLabels, requiring `QLabel.setBuddy(input_widget)` for screen reader mnemonic focus. Screen readers also struggle with emojis, so stripping targeted emoji Unicode ranges is necessary for `accessibleName`.
**Action:** Always manually set buddy relationships for composite widgets in PyQt6 and strip emojis from accessible names to prevent screen reader degradation.
