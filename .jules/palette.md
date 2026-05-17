## 2026-05-17 - Missing Screen Reader Associations in Composite Forms
**Learning:** The `FormRow` custom component in `core_widgets.py` groups a `QLabel` and an input widget in an `HBoxLayout` but doesn't explicitly link them. This causes screen readers to announce the input fields without context.
**Action:** Always call `label.setBuddy(input_widget)` when manually pairing labels with inputs outside of `QFormLayout.addRow("String", widget)` to ensure proper accessibility and keyboard mnemonic focus.
