## 2024-05-25 - FormRow Accessibility Improvement
**Learning:** In PyQt6, composite form components (like `FormRow`) where a `QLabel` is placed next to an input widget do not automatically associate the label with the input field for screen readers. Explicitly calling `QLabel.setBuddy(input_widget)` is required for accessibility and keyboard focus support.
**Action:** Add `lbl.setBuddy(input_widget)` to the `FormRow` widget in `ui/components/core_widgets.py` to improve general UI accessibility across the application.
