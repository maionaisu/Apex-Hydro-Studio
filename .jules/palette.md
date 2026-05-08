## 2024-05-08 - Accessible Names and Form Controls
**Learning:** Screen readers struggle with emojis commonly used in ModernButton labels, and FormRow labels do not natively associate with their input widgets, degrading form accessibility.
**Action:** Implemented `setBuddy()` in `FormRow` to properly link labels to inputs, ensuring screen readers announce the label correctly when focusing the input. Stripped emojis from button text and assigned it via `setAccessibleName()` in `ModernButton` to ensure clean readouts.
