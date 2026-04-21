from PyQt6.QtWidgets import QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy
from PyQt6.QtCore import Qt, QRect, QRectF, QPoint
from PyQt6.QtGui import QPainter, QPainterPath, QColor, QPen

class InteractiveTourOverlay(QWidget):
    """
    Overlay to display interactive tours/tips guiding users through the UI.
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
        self.btn_next.setStyleSheet("background-color: #F59E0B; color: #022C22; font-weight: 800; padding: 8px; border-radius: 6px;")
        self.btn_next.clicked.connect(self.next_step)
        
        self.btn_close = QPushButton("Tutup")
        self.btn_close.setStyleSheet("background-color: transparent; color: #94A3B8; border: 1px solid #475569; font-weight: bold; padding: 8px; border-radius: 6px;")
        self.btn_close.clicked.connect(self.hide_tour)
        
        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.btn_close)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_next)
        
        self.info_layout.addWidget(self.lbl_title)
        self.info_layout.addWidget(self.lbl_desc)
        self.info_layout.addSpacing(5)
        self.info_layout.addLayout(btn_layout)

    def set_steps(self, steps): 
        self.steps = steps

    def start_tour(self):
        if not self.steps: return
        self.current_step = 0
        if self.parent():
            self.resize(self.parent().size())
        self.show()
        self.raise_()
        self.update_step()

    def next_step(self):
        self.current_step += 1
        if self.current_step >= len(self.steps): 
            self.hide_tour()
        else: 
            self.update_step()

    def hide_tour(self): 
        self.hide()

    def update_step(self):
        step = self.steps[self.current_step]
        self.lbl_title.setText(step['title'])
        self.lbl_desc.setText(step['desc'])
        self.btn_next.setText("Selesai" if self.current_step == len(self.steps) - 1 else "Lanjut ➔")
        self.info_box.adjustSize()
        
        widget = step['widget']
        if widget:
            global_pos_tl = widget.mapToGlobal(QPoint(0,0))
            local_pos_tl = self.mapFromGlobal(global_pos_tl)
            global_pos_br = widget.mapToGlobal(QPoint(widget.width(), widget.height()))
            local_pos_br = self.mapFromGlobal(global_pos_br)
            
            self.target_rect = QRect(local_pos_tl, local_pos_br).adjusted(-8, -8, 8, 8)
            box_w = self.info_box.width()
            box_h = self.info_box.height()
            screen_w = self.width()
            screen_h = self.height()
            
            x = local_pos_br.x() + 20
            if x + box_w > screen_w: x = local_pos_tl.x() - box_w - 20
            y = local_pos_tl.y()
            if y + box_h > screen_h: y = screen_h - box_h - 20
            self.info_box.move(max(10, x), max(10, y))
        else:
            self.target_rect = QRect(0,0,0,0)
            self.info_box.move(self.width()//2 - self.info_box.width()//2, self.height()//2 - self.info_box.height()//2)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        path = QPainterPath()
        path.addRect(QRectF(self.rect()))
        
        if not self.target_rect.isEmpty():
            hole = QPainterPath()
            hole.addRoundedRect(QRectF(self.target_rect), 8, 8)
            path.addPath(hole)
            
        path.setFillRule(Qt.FillRule.OddEvenFill)
        painter.fillPath(path, QColor(0, 0, 0, 220))
        
        if not self.target_rect.isEmpty():
            pen = QPen(QColor(245, 158, 11))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.drawRoundedRect(self.target_rect, 8, 8)
