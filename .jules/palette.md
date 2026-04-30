## 2024-05-01 - [Label-to-Input Association in PyQt6]
**Learning:** Found that custom layout wrappers (like `FormRow` which manually pairs a `QLabel` with an input widget) naturally lose their native screen-reader and keyboard shortcut linkages unless explicitly bonded.
**Action:** Always use `QLabel.setBuddy(input_widget)` when constructing composite form controls so accessibility tools correctly announce the label for the given input field.
