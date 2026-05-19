## 2024-05-19 - QFormLayout Accessibility
**Learning:** In PyQt6, `QFormLayout.addRow("String", widget)` automatically creates a label and sets the buddy. However, `QFormLayout.addRow(QLabel, widget)` does NOT auto-set the buddy. This breaks screen reader support for the form row.
**Action:** When passing pre-existing `QLabel` instances to `QFormLayout.addRow(QLabel, widget)`, you must manually call `label.setBuddy(widget)` to ensure proper screen reader support and keyboard accessibility.
