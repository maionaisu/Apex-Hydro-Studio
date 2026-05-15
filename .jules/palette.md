## 2026-05-15 - [Add Buddy Label Linking in Composite Form Widgets]
**Learning:** When using composite layout controls in PyQt, linking a QLabel to its input widget using setBuddy() ensures screen readers correctly announce the input's purpose and enables keyboard navigation/focus mapping. Form layout wrappers built manually with QHBoxLayout/QVBoxLayout must explicitly wire this, unlike QFormLayout which handles it implicitly when passed a string.
**Action:** Ensure all custom form label-input pairing wrappers implement setBuddy() on initialization.
