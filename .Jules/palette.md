## 2024-05-18 - Added ToolTips and Accessible Names to ERA5 Wave Inputs
**Learning:** Added `setToolTip` and `setAccessibleName` to QLineEdit fields with domain-specific acronyms (`Hs`, `Tp`, `Dir`) in `ui/views/modul1_era5.py` to improve screen reader accessibility and context.
**Action:** Ensure UI elements with acronyms or placeholders that disappear on focus have proper tooltips and accessible names.
