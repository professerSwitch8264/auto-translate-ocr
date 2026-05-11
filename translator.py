import sys
import types
import mss
import numpy as np
import pytesseract
import re
import json
import os
import webbrowser
import keyboard
from concurrent.futures import ThreadPoolExecutor
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QLineEdit, QFormLayout
from PySide6.QtCore import Qt, QPoint, QRect, QTimer, Signal, QObject
from PySide6.QtGui import QPainter, QPen, QColor
from googletrans import Translator
from PIL import Image

try:
    import cgi
except ImportError:
    sys.modules['cgi'] = types.ModuleType('cgi')

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

class Communicate(QObject):
    update_signal = Signal(str)
    vocab_signal = Signal(list)
    hk_crop = Signal()
    hk_preview = Signal()
    hk_auto = Signal()
    hk_trans = Signal()
    hk_show_trans = Signal()

class SettingsBox(QWidget):
    settings_saved = Signal(dict)
    settings_closed = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setGeometry(150, 150, 300, 300)
        
        self.hotkeys_enabled = True
        
        self.container = QFrame()
        self.container.setStyleSheet("""
            QFrame {
                background-color: rgba(15, 15, 15, 240);
                border: 2px solid #d4af37;
                border-radius: 4px;
            }
            QLabel { color: #eeeeee; font-weight: bold; border: none; background: transparent; }
            QLineEdit {
                background-color: #333333;
                color: #d4af37;
                border: 1px solid #666666;
                padding: 4px;
                border-radius: 2px;
                font-family: 'Consolas', monospace;
            }
            QLineEdit:focus { border: 1px solid #d4af37; }
        """)
        
        layout = QVBoxLayout(self.container)
        
        title = QLabel("ตั้งค่าคีย์ลัด (เช่น f2, alt+q)")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        self.btn_toggle_hk = QPushButton("สถานะคีย์ลัด: เปิดใช้งาน")
        self.btn_toggle_hk.setFixedHeight(35)
        self.btn_toggle_hk.clicked.connect(self.action_toggle_hk)
        layout.addWidget(self.btn_toggle_hk)

        form_layout = QFormLayout()
        self.input_crop = QLineEdit()
        self.input_preview = QLineEdit()
        self.input_auto = QLineEdit()
        self.input_trans = QLineEdit()
        self.input_show_trans = QLineEdit()
        
        form_layout.addRow("ครอป:", self.input_crop)
        form_layout.addRow("พรีวิว:", self.input_preview)
        form_layout.addRow("ออโต้:", self.input_auto)
        form_layout.addRow("แปล:", self.input_trans)
        form_layout.addRow("ซ่อน/โชว์แปล:", self.input_show_trans)
        layout.addLayout(form_layout)

        btn_layout = QHBoxLayout()
        self.btn_save = QPushButton("บันทึก")
        self.btn_close = QPushButton("ปิด")
        
        btn_style = """
            QPushButton {
                background-color: #1a1a1a;
                color: #d4af37;
                font-weight: bold;
                border: 2px solid #d4af37;
                border-radius: 4px;
                padding: 5px;
            }
            QPushButton:hover { background-color: #333; }
        """
        self.btn_save.setStyleSheet(btn_style)
        self.btn_close.setStyleSheet(btn_style)
        
        self.btn_save.clicked.connect(self.save_settings)
        self.btn_close.clicked.connect(self.close_settings)
        
        btn_layout.addWidget(self.btn_save)
        btn_layout.addWidget(self.btn_close)
        layout.addLayout(btn_layout)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.container)
        
        self.drag_pos = QPoint()

    def action_toggle_hk(self):
        self.hotkeys_enabled = not self.hotkeys_enabled
        self.update_toggle_style()

    def update_toggle_style(self):
        if self.hotkeys_enabled:
            self.btn_toggle_hk.setText("สถานะคีย์ลัด: เปิดใช้งาน")
            self.btn_toggle_hk.setStyleSheet("""
                QPushButton { background-color: #1a1a1a; color: #d4af37; font-weight: bold; border: 2px solid #d4af37; border-radius: 4px; }
                QPushButton:hover { background-color: #333; }
            """)
        else:
            self.btn_toggle_hk.setText("สถานะคีย์ลัด: ปิดใช้งาน")
            self.btn_toggle_hk.setStyleSheet("""
                QPushButton { background-color: #333333; color: #888888; font-weight: bold; border: 2px solid #666666; border-radius: 4px; }
                QPushButton:hover { background-color: #444444; }
            """)

    def load_settings(self, config):
        self.input_crop.setText(config.get("crop", "f2"))
        self.input_preview.setText(config.get("preview", "f3"))
        self.input_auto.setText(config.get("auto", "f4"))
        self.input_trans.setText(config.get("trans", "f5"))
        self.input_show_trans.setText(config.get("show_trans", "f6"))
        self.hotkeys_enabled = config.get("enabled", True)
        self.update_toggle_style()

    def save_settings(self):
        config = {
            "crop": self.input_crop.text().strip().lower(),
            "preview": self.input_preview.text().strip().lower(),
            "auto": self.input_auto.text().strip().lower(),
            "trans": self.input_trans.text().strip().lower(),
            "show_trans": self.input_show_trans.text().strip().lower(),
            "enabled": self.hotkeys_enabled
        }
        self.settings_saved.emit(config)
        self.hide()

    def close_settings(self):
        self.settings_closed.emit()
        self.hide()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_pos)

class ControlPanel(QWidget):
    def __init__(self, trigger_crop, toggle_auto, trigger_manual, toggle_preview, open_settings, toggle_show_trans):
        super().__init__()
        self.trigger_crop = trigger_crop
        self.toggle_auto = toggle_auto
        self.trigger_manual = trigger_manual
        self.toggle_preview = toggle_preview
        self.open_settings = open_settings
        self.toggle_show_trans = toggle_show_trans
        
        self.is_auto = True
        self.is_previewing = False
        self.is_show_trans = True
        self.hotkeys = {"crop": "f2", "preview": "f3", "auto": "f4", "trans": "f5", "show_trans": "f6", "enabled": True}
        
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        layout = QHBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(8)

        button_style = """
            QPushButton {
                background-color: #1a1a1a;
                color: #d4af37;
                font-weight: bold;
                border: 2px solid #d4af37;
                border-radius: 4px;
                padding: 0 10px;
                text-align: center;
            }
            QPushButton:hover { background-color: #333; color: #f1c40f; }
        """

        self.btn_move = QPushButton("ย้าย")
        self.btn_move.setFixedSize(50, 55)
        self.btn_move.setCursor(Qt.CursorShape.SizeAllCursor)
        self.btn_move.setStyleSheet(button_style)

        self.btn_setting = QPushButton("ตั้งค่า")
        self.btn_setting.setFixedHeight(55)
        self.btn_setting.setStyleSheet(button_style)
        self.btn_setting.clicked.connect(self.open_settings)
        
        self.btn_crop = QPushButton()
        self.btn_crop.setFixedHeight(55)
        self.btn_crop.setStyleSheet(button_style)
        self.btn_crop.clicked.connect(self.trigger_crop)

        self.btn_preview = QPushButton()
        self.btn_preview.setFixedHeight(55)
        self.btn_preview.setFixedWidth(85)
        self.btn_preview.clicked.connect(self.action_preview)

        self.btn_show_trans = QPushButton()
        self.btn_show_trans.setFixedHeight(55)
        self.btn_show_trans.setFixedWidth(90)
        self.btn_show_trans.clicked.connect(self.action_show_trans)

        self.btn_auto = QPushButton()
        self.btn_auto.setFixedHeight(55)
        self.btn_auto.setFixedWidth(85)
        self.btn_auto.clicked.connect(self.action_auto)

        self.btn_trans = QPushButton()
        self.btn_trans.setFixedHeight(55)
        self.btn_trans.setFixedWidth(50)
        self.btn_trans.setStyleSheet("""
            QPushButton {
                background-color: #d4af37;
                color: #1a1a1a;
                font-weight: bold;
                border: 2px solid #d4af37;
                border-radius: 4px;
                text-align: center;
            }
            QPushButton:hover { background-color: #f1c40f; }
            QPushButton:pressed { background-color: #aa8c2c; }
        """)
        self.btn_trans.clicked.connect(self.trigger_manual)

        self.btn_close = QPushButton("❌")
        self.btn_close.setFixedSize(40, 55)
        self.btn_close.setStyleSheet("""
            QPushButton {
                background-color: #8b0000;
                color: #eeeeee;
                font-size: 14px;
                font-weight: bold;
                border: 2px solid #ff4444;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #ff0000; }
        """)
        self.btn_close.clicked.connect(self.close_app)

        self.update_all_labels()

        layout.addWidget(self.btn_move)
        layout.addWidget(self.btn_crop)
        layout.addWidget(self.btn_preview)
        layout.addWidget(self.btn_show_trans)
        layout.addWidget(self.btn_auto)
        layout.addWidget(self.btn_trans)
        layout.addWidget(self.btn_setting)
        layout.addWidget(self.btn_close)
        self.setLayout(layout)
        
        self.setGeometry(100, 100, 610, 65)
        self.drag_pos = QPoint()

    def update_hotkeys(self, config):
        self.hotkeys = config
        self.update_all_labels()

    def update_all_labels(self):
        is_enabled = self.hotkeys.get('enabled', True)
        
        hk_crop = self.hotkeys.get('crop', '').upper() if is_enabled else ''
        self.btn_crop.setText(f"[ {hk_crop} ]\nเลือกจุดครอป" if hk_crop else "เลือกจุดครอป")
        
        hk_trans = self.hotkeys.get('trans', '').upper() if is_enabled else ''
        self.btn_trans.setText(f"[ {hk_trans} ]\nแปล" if hk_trans else "แปล")
        
        self.update_auto_style()
        self.update_preview_style()
        self.update_show_trans_style()

    def action_auto(self):
        self.is_auto = not self.is_auto
        self.toggle_auto(self.is_auto)
        self.update_auto_style()
        
    def action_preview(self):
        self.is_previewing = not self.is_previewing
        self.toggle_preview(self.is_previewing)
        self.update_preview_style()

    def action_show_trans(self):
        self.is_show_trans = not self.is_show_trans
        self.toggle_show_trans(self.is_show_trans)
        self.update_show_trans_style()

    def close_app(self):
        QApplication.instance().quit()

    def update_auto_style(self):
        is_enabled = self.hotkeys.get('enabled', True)
        hk = self.hotkeys.get('auto', '').upper() if is_enabled else ''
        hk_text = f"[ {hk} ]\n" if hk else ""
        
        if self.is_auto:
            self.btn_auto.setText(f"{hk_text}ออโต้: เปิด")
            self.btn_auto.setStyleSheet("""
                QPushButton { background-color: #1a1a1a; color: #d4af37; font-weight: bold; border: 2px solid #d4af37; border-radius: 4px; }
                QPushButton:hover { background-color: #333; }
            """)
        else:
            self.btn_auto.setText(f"{hk_text}ออโต้: ปิด")
            self.btn_auto.setStyleSheet("""
                QPushButton { background-color: #333333; color: #888888; font-weight: bold; border: 2px solid #666666; border-radius: 4px; }
                QPushButton:hover { background-color: #444444; }
            """)
            
    def update_preview_style(self):
        is_enabled = self.hotkeys.get('enabled', True)
        hk = self.hotkeys.get('preview', '').upper() if is_enabled else ''
        hk_text = f"[ {hk} ]\n" if hk else ""
        
        if self.is_previewing:
            self.btn_preview.setText(f"{hk_text}พรีวิว: เปิด")
            self.btn_preview.setStyleSheet("""
                QPushButton { background-color: #1a1a1a; color: #d4af37; font-weight: bold; border: 2px solid #d4af37; border-radius: 4px; }
                QPushButton:hover { background-color: #333; }
            """)
        else:
            self.btn_preview.setText(f"{hk_text}พรีวิว: ปิด")
            self.btn_preview.setStyleSheet("""
                QPushButton { background-color: #333333; color: #888888; font-weight: bold; border: 2px solid #666666; border-radius: 4px; }
                QPushButton:hover { background-color: #444444; }
            """)

    def update_show_trans_style(self):
        is_enabled = self.hotkeys.get('enabled', True)
        hk = self.hotkeys.get('show_trans', '').upper() if is_enabled else ''
        hk_text = f"[ {hk} ]\n" if hk else ""
        
        if self.is_show_trans:
            self.btn_show_trans.setText(f"{hk_text}กล่องแปล: เปิด")
            self.btn_show_trans.setStyleSheet("""
                QPushButton { background-color: #1a1a1a; color: #d4af37; font-weight: bold; border: 2px solid #d4af37; border-radius: 4px; }
                QPushButton:hover { background-color: #333; }
            """)
        else:
            self.btn_show_trans.setText(f"{hk_text}กล่องแปล: ปิด")
            self.btn_show_trans.setStyleSheet("""
                QPushButton { background-color: #333333; color: #888888; font-weight: bold; border: 2px solid #666666; border-radius: 4px; }
                QPushButton:hover { background-color: #444444; }
            """)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_pos)

class PreviewBox(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool | Qt.WindowType.WindowTransparentForInput)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def paintEvent(self, event):
        painter = QPainter(self)
        pen = QPen(QColor(0, 255, 0), 2)
        painter.setPen(pen)
        painter.drawRect(0, 0, self.width() - 1, self.height() - 1)

class TranslationBox(QWidget):
    def __init__(self, title, width=500):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # ล็อกความกว้างไว้ ความสูงจะเปลี่ยนอัตโนมัติ
        self.setFixedWidth(width)
        self.move(100, 100)
        
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        self.label = QLabel("")
        self.label.setStyleSheet("""
            background-color: rgba(15, 15, 15, 230);
            color: #eeeeee;
            font-size: 18px;
            font-family: 'Segoe UI', 'Tahoma';
            padding: 15px;
            border-left: 5px solid #d4af37;
            border-radius: 4px;
        """)
        self.label.setWordWrap(True)
        self.layout.addWidget(self.label)
        self.setLayout(self.layout)
        
        self.full_text = ""
        self.current_index = 0
        self.typing_timer = QTimer()
        self.typing_timer.timeout.connect(self.type_next_char)
        self.drag_pos = QPoint()
        self.click_pos = QPoint()

    def start_typing(self, text):
        if text != self.full_text:
            self.full_text = text
            self.current_index = 0
            self.label.setText("")
            self.adjustSize() # ย่อกล่องให้เล็กสุดก่อนพิมพ์
            self.typing_timer.start(20) 

    def type_next_char(self):
        if self.current_index < len(self.full_text):
            self.current_index += 1
            self.label.setText(self.full_text[:self.current_index])
            self.adjustSize() # อัปเดตความสูงเรื่อยๆ ตามข้อความที่เพิ่มขึ้น
        else:
            self.typing_timer.stop()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self.click_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_pos)

class ClickableVocabBox(QWidget):
    def __init__(self, size=(280, 250)):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setGeometry(100, 300, size[0], size[1])
        
        self.container = QFrame()
        self.container.setObjectName("vocabContainer")
        self.container.setStyleSheet("""
            #vocabContainer { background-color: rgba(15, 15, 15, 230); border-left: 5px solid #d4af37; border-radius: 4px; }
        """)
        
        self.inner_layout = QVBoxLayout(self.container)
        self.inner_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.container)
        
        self.drag_pos = QPoint()

    def update_vocab(self, vocab_list):
        for i in reversed(range(self.inner_layout.count())): 
            widget = self.inner_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()
        
        if not vocab_list:
            return

        title = QLabel("คลิกคำเพื่อเซฟ | '->' เพื่อดูเพิ่มเติม")
        title.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        title.setStyleSheet("color: #888888; font-size: 11px; font-weight: bold; border: none; padding-bottom: 5px;")
        self.inner_layout.addWidget(title)

        for word, meaning in vocab_list:
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(5)

            btn = QPushButton(f"{word} : {meaning}")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton { text-align: left; background: transparent; color: #eeeeee; font-size: 18px; border: none; padding: 3px 5px; }
                QPushButton:hover { color: #d4af37; }
            """)
            
            btn_search = QPushButton("->")
            btn_search.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_search.setFixedSize(25, 25)
            btn_search.setStyleSheet("""
                QPushButton { background-color: #333333; color: #eeeeee; font-size: 11px; font-weight: bold; border: 1px solid #555555; border-radius: 4px; }
                QPushButton:hover { background-color: #3498db; border: 1px solid #3498db; }
            """)

            btn.clicked.connect(lambda checked=False, w=word, m=meaning, b=btn: self.save_to_json(w, m, b))
            btn_search.clicked.connect(lambda checked=False, w=word: self.open_longdo_dict(w))

            row_layout.addWidget(btn)
            row_layout.addStretch()
            row_layout.addWidget(btn_search)

            self.inner_layout.addWidget(row_widget)
            
        QTimer.singleShot(10, self.adjustSize)

    def open_longdo_dict(self, word):
        url = f"https://dict.longdo.com/search/{word}"
        webbrowser.open(url)

    def save_to_json(self, word, meaning, btn):
        filename = "saved_vocab.json"
        data = {}
        if os.path.exists(filename):
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except:
                pass
        
        data[word] = meaning
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
            
        btn.setStyleSheet("""
            QPushButton { text-align: left; background: transparent; color: #f1c40f; font-size: 18px; border: none; padding: 3px 5px; }
        """)
        btn.setText(f"★ {word} : {meaning}")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_pos)

class ScreenCropper(QWidget):
    def __init__(self, callback):
        super().__init__()
        self.callback = callback
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.start_point = QPoint()
        self.end_point = QPoint()
        self.is_selecting = False

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 150))
        if self.is_selecting:
            painter.setPen(QPen(QColor(212, 175, 55), 2))
            painter.drawRect(QRect(self.start_point, self.end_point).normalized())

    def mousePressEvent(self, event):
        self.start_point = event.pos()
        self.is_selecting = True

    def mouseMoveEvent(self, event):
        if self.is_selecting:
            self.end_point = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_selecting = False
            rect = QRect(self.start_point, self.end_point).normalized()
            self.hide()
            self.callback(QRect(self.mapToGlobal(rect.topLeft()), rect.size()))

class TranslatorApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)
        self.c = Communicate()
        self.translator = Translator()
        self.config_file = "hotkeys.json"
        self.current_config = {}
        
        self.overlay = TranslationBox("Translation")
        self.c.update_signal.connect(self.overlay.start_typing)
        
        self.vocab_box = ClickableVocabBox()
        self.c.vocab_signal.connect(self.vocab_box.update_vocab)
        
        self.preview_box = PreviewBox()

        self.controls = ControlPanel(self.open_cropper, self.toggle_auto, self.manual_translate, self.toggle_preview, self.show_settings, self.toggle_show_trans)
        self.cropper = ScreenCropper(self.set_target_rect)
        self.controls.show()
        
        self.settings_box = SettingsBox()
        self.settings_box.settings_saved.connect(self.apply_hotkeys)
        self.settings_box.settings_closed.connect(self.restore_hotkeys)
        
        self.target_rect = None
        self.is_auto = True
        self.is_previewing = False
        self.is_show_trans = True
        self.is_processing = False
        self.dpi_ratio = 1.0 
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.last_raw_text = ""
        
        self.c.hk_crop.connect(self.controls.btn_crop.click)
        self.c.hk_preview.connect(self.controls.btn_preview.click)
        self.c.hk_auto.connect(self.controls.btn_auto.click)
        self.c.hk_trans.connect(self.controls.btn_trans.click)
        self.c.hk_show_trans.connect(self.controls.btn_show_trans.click)

        self.load_hotkeys()
        
        self.timer = QTimer()
        self.timer.timeout.connect(self.auto_process)
        self.timer.start(1500)

    def show_settings(self):
        keyboard.unhook_all() 
        self.settings_box.show()
        self.settings_box.raise_()

    def load_hotkeys(self):
        default_config = {"crop": "f2", "preview": "f3", "auto": "f4", "trans": "f5", "show_trans": "f6", "enabled": True}
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            except:
                config = default_config
        else:
            config = default_config
            
        self.settings_box.load_settings(config)
        self.apply_hotkeys(config)

    def restore_hotkeys(self):
        self.apply_hotkeys(self.current_config)

    def apply_hotkeys(self, config):
        self.current_config = config
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4)
            
        self.controls.update_hotkeys(config)
        keyboard.unhook_all()
        
        if config.get("enabled", True):
            try:
                if config["crop"]: keyboard.add_hotkey(config["crop"], self.c.hk_crop.emit)
                if config["preview"]: keyboard.add_hotkey(config["preview"], self.c.hk_preview.emit)
                if config["auto"]: keyboard.add_hotkey(config["auto"], self.c.hk_auto.emit)
                if config["trans"]: keyboard.add_hotkey(config["trans"], self.c.hk_trans.emit)
                if config.get("show_trans"): keyboard.add_hotkey(config["show_trans"], self.c.hk_show_trans.emit)
                self.overlay.start_typing(f"[อัปเดตระบบคีย์ลัดพร้อมใช้งาน]")
            except Exception as e:
                self.overlay.start_typing(f"[เกิดข้อผิดพลาด: ตรวจสอบการสะกดชื่อปุ่มให้ถูกต้อง]")
        else:
            self.overlay.start_typing(f"[ระบบคีย์ลัดถูกปิดใช้งาน]")

    def open_cropper(self):
        self.cropper.showFullScreen()

    def toggle_auto(self, is_auto):
        self.is_auto = is_auto
        if is_auto:
            self.overlay.start_typing("[ระบบอัตโนมัติเปิดทำงาน]")
        else:
            self.overlay.start_typing("[ระบบอัตโนมัติถูกปิด - กดปุ่ม 'แปล' เพื่อแปลเอง]")
            
    def toggle_preview(self, is_previewing):
        self.is_previewing = is_previewing
        if self.is_previewing and self.target_rect:
            self.preview_box.setGeometry(self.target_rect)
            self.preview_box.show()
        else:
            self.preview_box.hide()

    def toggle_show_trans(self, is_showing):
        self.is_show_trans = is_showing
        if self.is_show_trans and self.target_rect:
            self.overlay.show()
        else:
            self.overlay.hide()

    def manual_translate(self):
        if self.target_rect and not self.is_processing:
            self.overlay.start_typing("กำลังแปล...")
            self.executor.submit(self.translate_worker)
        elif not self.target_rect:
            self.overlay.start_typing("[กรุณาเลือกจุดครอปก่อน]")

    def set_target_rect(self, rect):
        if rect.width() > 10:
            self.target_rect = rect
            try:
                self.dpi_ratio = self.cropper.devicePixelRatioF()
            except AttributeError:
                self.dpi_ratio = self.cropper.devicePixelRatio()
                
            if self.is_show_trans:
                self.overlay.show()
                
            self.vocab_box.show()
            self.vocab_box.move(self.overlay.x() + 510, self.overlay.y())
            
            if self.is_previewing:
                self.preview_box.setGeometry(self.target_rect)
                self.preview_box.show()
            
            self.last_raw_text = ""
            self.overlay.start_typing("ล็อคพื้นที่แล้ว กำลังแปลทันที...")
            
            if not self.is_processing:
                self.executor.submit(self.translate_worker)

    def auto_process(self):
        if self.is_auto and self.target_rect and not self.is_processing:
            self.executor.submit(self.translate_worker)

    def translate_worker(self):
        self.is_processing = True
        try:
            with mss.mss() as sct:
                r = getattr(self, 'dpi_ratio', 1.0)
                monitor = {
                    "top": int(self.target_rect.y() * r), 
                    "left": int(self.target_rect.x() * r), 
                    "width": int(self.target_rect.width() * r), 
                    "height": int(self.target_rect.height() * r)
                }
                
                img = Image.frombytes("RGB", sct.grab(monitor).size, sct.grab(monitor).bgra, "raw", "BGRX")
                raw_text = pytesseract.image_to_string(img, lang='eng', config='--psm 6').strip()
                raw_text = re.sub(r'\s+', ' ', raw_text.replace('\n', ' '))
                
                if not raw_text or (raw_text == self.last_raw_text and self.is_auto):
                    self.is_processing = False
                    return

                self.last_raw_text = raw_text
                main_trans = self.translator.translate(raw_text, src='en', dest='th').text
                self.c.update_signal.emit(main_trans)
                
                seen = set()
                words_in_order = []
                for w in re.findall(r'\b\w{3,}\b', raw_text):
                    lw = w.lower()
                    if lw not in seen:
                        seen.add(lw)
                        words_in_order.append(lw)

                vocab_data = []
                for w in words_in_order:
                    tw = self.translator.translate(w, src='en', dest='th').text
                    vocab_data.append((w, tw))
                
                self.c.vocab_signal.emit(vocab_data)
                    
        except Exception as e:
            print(f"Error: {e}")
            self.c.update_signal.emit("[ไม่สามารถดึงคำแปลได้ ลองกดแปลใหม่อีกครั้ง]")
        finally:
            self.is_processing = False

    def run(self):
        sys.exit(self.app.exec())

if __name__ == "__main__":
    app = TranslatorApp()
    app.run()