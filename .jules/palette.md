## 2024-05-24 - Accessibility Enhancements for PyQt6 Custom Widgets
**Learning:** Screen readers struggle with emojis in button text, and custom composite layout controls (like `FormRow` containing a `QLabel` and input widget) do not automatically link the label to the input for accessibility.
**Action:** Use targeted regular expressions to strip emojis before calling `setAccessibleName()` on buttons, ensuring clear ARIA labels. Always call `QLabel.setBuddy(input_widget)` within custom form layouts to explicitly link the label and input.
