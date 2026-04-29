# ==============================================================================
# APEX NEXUS TIER-0: CORE UI WIDGETS & FLEXBOX INFRASTRUCTURE
# Engine: PyQt6 / PySide6
# Description: Defines the foundational building blocks for a fluid, breathable,
#              and non-collapsing enterprise GUI.
# ==============================================================================
import logging
import re
from PyQt6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QSizePolicy, QScrollArea
)
from PyQt6.QtCore import Qt, QRect, QRectF, QPoint, QEvent
from PyQt6.QtGui import QPainter, QPainterPath, QColor, QPen

logger = logging.getLogger(__name__)

# ==============================================================================
# 1. FLEXBOX LAYOUT CONTAINERS (THE CURE FOR "CEMET" UI)
# ==============================================================================

class FlexScrollArea(QScrollArea):
    """
    [TIER-0] Base layout container for all modules.
    Ensures widgets expand gracefully and provide a scrollbar when compressed,
    completely eliminating the PyQt "squished/cemet" UI anomaly.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet("background: transparent; border: none;")
        
        self.container = QWidget()
        self.container.setObjectName("ScrollContainer")
        self.container.setStyleSheet("background: transparent;")
        
        self.flex_layout = QVBoxLayout(self.container)
        self.flex_layout.setContentsMargins(16, 16, 16, 16)
        self.flex_layout.setSpacing(16)
        self.flex_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self.setWidget(self.container)
        
    def add_widget(self, widget: QWidget):
        self.flex_layout.addWidget(widget)
        
    def add_layout(self, layout):
        self.flex_layout.addLayout(layout)
        
    def add_stretch(self, stretch: int = 1):
        self.flex_layout.addStretch(stretch)

class CardWidget(QFrame):
    """
    [TIER-0] Standardized Dashboard Card. 
    Acts as a CSS flex-column with safe layout constraints.
    """
    def __init__(self, title: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("CardWidget")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.setStyleSheet("QFrame#CardWidget { background-color: #2D3139; border: 1px solid #3A3F4A; border-radius: 12px; }")
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(20, 20, 20, 20)
        self.layout.setSpacing(16)
        
        if title:
            self.lbl_title = QLabel(title)
            self.lbl_title.setStyleSheet("font-size: 14px; font-weight: 900; color: #8FC9DC; margin-bottom: 4px; border: none;")
            self.layout.addWidget(self.lbl_title)

    def add_widget(self, widget: QWidget):
        self.layout.addWidget(widget)

    def add_layout(self, layout):
        self.layout.addLayout(layout)

# ==============================================================================
# 2. UI COMPONENTS & CONTROLS
# ==============================================================================

class FormRow(QWidget):
    """
    [TIER-0] Form layout component.
    Aligns a label on the left and an input widget on the right.
    Hardened with WordWrap and size constraints to prevent layout breaking.
    """
    def __init__(self, label_text: str, input_widget: QWidget, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        
        lbl = QLabel(label_text)
        lbl.setStyleSheet("color: #E2E8F0; font-weight: 600; font-size: 13px; border: none;")
        lbl.setMinimumWidth(180) # Memberi ruang proporsional
        lbl.setWordWrap(True)
        lbl.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        
        input_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        
        layout.addWidget(lbl)
        layout.addWidget(input_widget)

class ModernButton(QPushButton):
    """
    [TIER-0] Standardized enterprise button mapping to QSS states.
    Equipped with Async Guard (set_loading) to prevent double-click worker crashes.
    """
    def __init__(self, text: str, btn_type: str = "primary", parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._original_text = text
        
        # Safely remove common UI emojis/symbols without stripping international characters
        self._emoji_pattern = r'[\U00010000-\U0010ffff\u25A0-\u25FF\u2700-\u27BF\u2600-\u26FF\u2B00-\u2BFF\u2300-\u23FF◀▶➔⏳■✅❌⚠]'
        clean_text = re.sub(self._emoji_pattern, '', text).strip()
        if clean_text:
            self.setAccessibleName(clean_text)

        if btn_type == "primary":
            self.setObjectName("PrimaryBtn")
        elif btn_type == "outline":
            self.setObjectName("OutlineBtn")
        elif btn_type == "danger":
            self.setObjectName("DangerBtn")
            
    def set_loading(self, is_loading: bool, loading_text: str = "⏳ Memproses...") -> None:
        """[ENTERPRISE SAFEGUARD]: Cegah double-submission / race condition UI."""
        self.setEnabled(not is_loading)
        if is_loading:
            self._original_text = self.text()
            self.setText(loading_text)
            clean_loading_text = re.sub(self._emoji_pattern, '', loading_text).strip()
            if clean_loading_text:
                self.setAccessibleName(clean_loading_text)
        else:
            self.setText(self._original_text)
            clean_original_text = re.sub(self._emoji_pattern, '', self._original_text).strip()
            # Always reset accessible name when going back, even if empty (fallback to default Qt behavior)
            self.setAccessibleName(clean_original_text if clean_original_text else "")

# ==============================================================================
# 3. INTERACTIVE TOUR OVERLAY (HARDENED)
# ==============================================================================

class InteractiveTourOverlay(QWidget):
    """
    [TIER-0] Overlay to display interactive tours/tips.
    Hardened with boundary clamping, parent resize event hooking, and C++ object deletion protection.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.hide()
        
        self.current_step = 0
        self.steps = []
        self.target_rect = QRect(0, 0, 0, 0)
        
        self.info_box = QFrame(self)
        self.info_box.setStyleSheet("background-color: #0F172A; border: 1px solid #F59E0B; border-radius: 12px; padding: 20px; width: 340px;")
        
        self.info_layout = QVBoxLayout(self.info_box)
        self.info_layout.setSpacing(10)
        
        self.lbl_title = QLabel()
        self.lbl_title.setStyleSheet("font-size: 15px; font-weight: 900; color: #F59E0B; border: none;")
        
        self.lbl_desc = QLabel()
        self.lbl_desc.setStyleSheet("font-size: 13px; color: #E2E8F0; border: none; line-height: 1.5;")
        self.lbl_desc.setWordWrap(True)
        self.lbl_desc.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        
        self.btn_next = QPushButton("Lanjut ➔")
        self.btn_next.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_next.setStyleSheet("background-color: #F59E0B; color: #022C22; font-weight: 800; padding: 8px 16px; border-radius: 6px; border: none;")
        self.btn_next.clicked.connect(self.next_step)
        
        self.btn_close = QPushButton("Tutup")
        self.btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close.setStyleSheet("background-color: transparent; color: #94A3B8; border: 1px solid #475569; font-weight: bold; padding: 8px 16px; border-radius: 6px;")
        self.btn_close.clicked.connect(self.hide_tour)
        
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 8, 0, 0)
        btn_layout.addWidget(self.btn_close)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_next)
        
        self.info_layout.addWidget(self.lbl_title)
        self.info_layout.addWidget(self.lbl_desc)
        self.info_layout.addLayout(btn_layout)

    def setParent(self, parent):
        """[ENTERPRISE FIX]: Event Filter Injection untuk melacak Resize Parent."""
        if self.parent():
            self.parent().removeEventFilter(self)
        super().setParent(parent)
        if parent:
            parent.installEventFilter(self)

    def eventFilter(self, obj, event):
        """Mencegah overlay tidak menutupi seluruh layar saat jendela dibesarkan/dikecilkan."""
        if obj == self.parent() and event.type() == QEvent.Type.Resize:
            if self.isVisible():
                self.resize(event.size())
                self.update_step() # Hitung ulang target lubang fokus
        return super().eventFilter(obj, event)

    def set_steps(self, steps: list) -> None: 
        if not isinstance(steps, list):
            logger.error("[TOUR] 'steps' must be a list of dictionaries.")
            return
        self.steps = steps

    def start_tour(self) -> None:
        if not self.steps: return
        self.current_step = 0
        if self.parent(): self.resize(self.parent().size())
        self.show()
        self.raise_()
        self.update_step()

    def next_step(self) -> None:
        self.current_step += 1
        if self.current_step >= len(self.steps): self.hide_tour()
        else: self.update_step()

    def hide_tour(self) -> None: 
        self.hide()

    def update_step(self) -> None:
        try:
            step = self.steps[self.current_step]
            self.lbl_title.setText(step.get('title', 'Tutorial'))
            self.lbl_desc.setText(step.get('desc', '...'))
            self.btn_next.setText("Selesai" if self.current_step == len(self.steps) - 1 else "Lanjut ➔")
            
            self.info_box.adjustSize()
            widget = step.get('widget')
            
            is_valid_widget = False
            if widget:
                try:
                    is_valid_widget = not widget.isHidden() and widget.isVisible()
                except RuntimeError:
                    is_valid_widget = False

            if is_valid_widget:
                try:
                    global_pos_tl = widget.mapToGlobal(QPoint(0,0))
                    local_pos_tl = self.mapFromGlobal(global_pos_tl)
                    
                    global_pos_br = widget.mapToGlobal(QPoint(widget.width(), widget.height()))
                    local_pos_br = self.mapFromGlobal(global_pos_br)
                    
                    self.target_rect = QRect(local_pos_tl, local_pos_br).adjusted(-8, -8, 8, 8)
                    
                    box_w, box_h = self.info_box.width(), self.info_box.height()
                    screen_w, screen_h = self.width(), self.height()
                    
                    x = local_pos_br.x() + 20
                    if x + box_w > screen_w: x = local_pos_tl.x() - box_w - 20
                    y = local_pos_tl.y()
                    if y + box_h > screen_h: y = screen_h - box_h - 20
                        
                    self.info_box.move(max(10, x), max(10, y))
                except Exception:
                    self.target_rect = QRect(0,0,0,0) 
            else:
                self.target_rect = QRect(0,0,0,0)
                self.info_box.move(max(0, self.width()//2 - self.info_box.width()//2), 
                                   max(0, self.height()//2 - self.info_box.height()//2))
            self.update() 
            
        except Exception as e:
            logger.error(f"[TOUR] Failed step {self.current_step}: {str(e)}")
            self.hide_tour()

    def paintEvent(self, event) -> None:
        if self.width() <= 0 or self.height() <= 0: return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRect(QRectF(self.rect()))
        
        if not self.target_rect.isEmpty():
            hole = QPainterPath()
            hole.addRoundedRect(QRectF(self.target_rect), 8, 8)
            path.addPath(hole)
            
        path.setFillRule(Qt.FillRule.OddEvenFill)
        painter.fillPath(path, QColor(15, 23, 42, 200)) # Slate-900 with alpha
        
        if not self.target_rect.isEmpty():
            pen = QPen(QColor(245, 158, 11))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.drawRoundedRect(self.target_rect, 8, 8)
