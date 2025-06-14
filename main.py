import sys
import os
import asyncio
import edge_tts
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QTextEdit, QPushButton, QComboBox, 
                            QLabel, QFileDialog, QMessageBox, QProgressBar,
                            QTabWidget, QLineEdit, QListWidget, QListWidgetItem,
                            QScrollArea)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QUrl, QTimer
from PyQt5.QtWebEngineWidgets import QWebEngineView
from gtts import gTTS
import tempfile
import pyttsx3
import json
import pygame
import time
# Thêm import cho OpenAI
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None
from google.cloud import texttospeech
from google import genai  # CHUẨN MỚI
from PyQt5.QtGui import QIcon, QClipboard, QPixmap
import re
import requests
from io import BytesIO

VIETNAMESE_VOICES = [
    ("vi-VN-Standard-A", "Nữ - Tiêu chuẩn"),
    ("vi-VN-Standard-B", "Nam - Tiêu chuẩn"),
    ("vi-VN-Standard-C", "Nữ - Tiêu chuẩn"),
    ("vi-VN-Standard-D", "Nam - Tiêu chuẩn"),
    ("vi-VN-Wavenet-A", "Nữ - WaveNet (AI)"),
    ("vi-VN-Wavenet-B", "Nam - WaveNet (AI)"),
    ("vi-VN-Wavenet-C", "Nữ - WaveNet (AI)"),
    ("vi-VN-Wavenet-D", "Nam - WaveNet (AI)"),
    ("vi-VN-Neural2-A", "Nữ - Neural2 (AI Mới)"),
    ("vi-VN-Neural2-D", "Nam - Neural2 (AI Mới)")
]

CONFIG_FILE = "config.json"

# Thêm từ điển ngôn ngữ
LANGS = {
    'vi': {
        'app_title': 'Chuyển Văn Bản Thành Giọng Nói',
        'edge_tab': 'Edge TTS',
        'gemini_tab': 'Gemini TTS',
        'google_tab': 'Google TTS',
        'openai_tab': 'OpenAI TTS',
        'input_placeholder': 'Nhập văn bản cần chuyển thành giọng nói...',
        'choose_voice': 'Chọn giọng đọc:',
        'convert_btn': 'Chuyển thành giọng nói',
        'save_btn': 'Lưu file âm thanh',
        'status_converting': 'Đang chuyển đổi...',
        'status_success': 'Chuyển đổi thành công!',
        'status_error': 'Lỗi',
        'warning_no_text': 'Vui lòng nhập văn bản!',
        'warning_no_key': 'Vui lòng nhập API Key!',
        'warning_no_json': 'Vui lòng chọn file JSON key hợp lệ!',
        'choose_json_btn': 'Chọn file JSON key',
        'no_json': 'Chưa chọn file JSON key',
        'copied': 'Đã sao chép!',
        'api_key': 'API Key:',
        'gemini_api_key': 'Gemini API Key:',
        'openai_api_key': 'OpenAI API Key:',
        'language': 'Ngôn ngữ giao diện:',
    },
    'en': {
        'app_title': 'Text to Speech Converter',
        'edge_tab': 'Edge TTS',
        'gemini_tab': 'Gemini TTS',
        'google_tab': 'Google TTS',
        'openai_tab': 'OpenAI TTS',
        'input_placeholder': 'Enter text to convert to speech...',
        'choose_voice': 'Select voice:',
        'convert_btn': 'Convert to Speech',
        'save_btn': 'Save Audio File',
        'status_converting': 'Converting...',
        'status_success': 'Conversion successful!',
        'status_error': 'Error',
        'warning_no_text': 'Please enter text!',
        'warning_no_key': 'Please enter API Key!',
        'warning_no_json': 'Please select a valid JSON key file!',
        'choose_json_btn': 'Choose JSON key file',
        'no_json': 'No JSON key file selected',
        'copied': 'Copied!',
        'api_key': 'API Key:',
        'gemini_api_key': 'Gemini API Key:',
        'openai_api_key': 'OpenAI API Key:',
        'language': 'UI Language:',
    }
}

# Thêm biến ngôn ngữ hiện tại
CURRENT_LANG = 'vi'

def tr(key):
    return LANGS[CURRENT_LANG].get(key, key)

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_config(config):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

class AudioPlayerThread(QThread):
    finished = pyqtSignal()
    def __init__(self, audio_file):
        super().__init__()
        self.audio_file = audio_file
        self._stop = False
    def run(self):
        try:
            pygame.mixer.init()
            pygame.mixer.music.load(self.audio_file)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                if self._stop:
                    pygame.mixer.music.stop()
                    break
                time.sleep(0.1)
        except Exception:
            pass
        self.finished.emit()
    def stop(self):
        self._stop = True
        if pygame.mixer.get_init():
            pygame.mixer.music.stop()

class TTSThread(QThread):
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, text, voice, output_file):
        super().__init__()
        self.text = text
        self.voice = voice
        self.output_file = output_file

    async def generate_speech(self):
        try:
            communicate = edge_tts.Communicate(self.text, self.voice)
            await communicate.save(self.output_file)
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))

    def run(self):
        asyncio.run(self.generate_speech())

class ChatBubbleWidget(QWidget):
    def __init__(self, text, is_user, animate_lines=False, parent_listwidget=None):
        super().__init__()
        self.is_user = is_user
        self.animate_lines = animate_lines
        self.parent_listwidget = parent_listwidget
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 5, 10, 5)
        if is_user:
            self.text_label = QLabel(text)
            self.text_label.setWordWrap(True)
            self.text_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            self.text_label.setStyleSheet("""
                QLabel {
                    background-color: #e3f2fd;
                    color: #000;
                    padding: 10px;
                    border-radius: 10px;
                    font-size: 14px;
                    line-height: 1.4;
                    text-align: left;
                }
            """)
            layout.addWidget(self.text_label)
        else:
            # Bot: dùng QScrollArea chứa QLabel để cuộn được
            self.text_label = QLabel("")
            self.text_label.setWordWrap(True)
            self.text_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            self.text_label.setStyleSheet("""
                QLabel {
                    background-color: #f5f5f5;
                    color: #222;
                    padding: 10px;
                    border-radius: 10px;
                    font-size: 14px;
                    line-height: 1.4;
                    text-align: left;
                }
            """)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            scroll.setWidget(self.text_label)
            scroll.setMinimumHeight(40)
            scroll.setMaximumHeight(300)
            layout.addWidget(scroll)
            # Hiệu ứng chạy từng dòng
            if animate_lines:
                self.lines = text.split('\n')
                self.current_line = 0
                self.animated_text = ""
                self.timer = QTimer(self)
                self.timer.timeout.connect(self.show_next_line)
                self.timer.start(60)  # 60ms mỗi dòng, có thể chỉnh
            else:
                self.text_label.setText(text)
        if not is_user:
            def copy_and_notify():
                QApplication.clipboard().setText(self.text_label.text())
                notify = QLabel("Đã sao chép!")
                notify.setStyleSheet("""
                    QLabel {
                        background: rgba(0,0,0,0.7);
                        color: #fff;
                        border-radius: 8px;
                        padding: 4px 16px;
                        font-size: 13px;
                        margin: 0px;
                    }
                """)
                notify.setWindowFlags(Qt.ToolTip)
                notify.setAttribute(Qt.WA_TranslucentBackground)
                notify.setAlignment(Qt.AlignCenter)
                notify.setParent(self)
                notify.move(self.width() - notify.sizeHint().width() - 20, 5)
                notify.show()
                QTimer.singleShot(1000, notify.deleteLater)
            copy_btn = QPushButton("📋")
            copy_btn.setToolTip("Sao chép")
            copy_btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    border: none;
                    font-size: 16px;
                    padding: 2px;
                }
                QPushButton:hover {
                    background: rgba(0,0,0,0.1);
                    border-radius: 3px;
                }
            """)
            copy_btn.clicked.connect(copy_and_notify)
            layout.addWidget(copy_btn, alignment=Qt.AlignRight)
        self.setLayout(layout)
        self.setStyleSheet("""
            QWidget {
                background-color: transparent;
            }
        """)
    def show_next_line(self):
        if self.current_line < len(self.lines):
            if self.animated_text:
                self.animated_text += '\n'
            self.animated_text += self.lines[self.current_line]
            self.text_label.setText(self.animated_text)
            self.current_line += 1
            # Tự động cuộn xuống cuối nếu có parent_listwidget
            if self.parent_listwidget:
                self.parent_listwidget.scrollToBottom()
        else:
            self.timer.stop()

class LoadingBubbleWidget(QWidget):
    def __init__(self, is_user=False):
        super().__init__()
        layout = QHBoxLayout()
        layout.setContentsMargins(5, 2, 5, 2)
        if is_user:
            layout.addStretch()
        self.label = QLabel("Đang phản hồi")
        self.label.setStyleSheet("color: #888;")
        layout.addWidget(self.label)
        if not is_user:
            layout.addStretch()
        self.setLayout(layout)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.animate)
        self.dot_count = 0
        self.timer.start(400)
    def animate(self):
        self.dot_count = (self.dot_count + 1) % 4
        self.label.setText("Đang phản hồi" + "." * self.dot_count)

class TextToSpeechApp(QMainWindow):
    def __init__(self):
        super().__init__()
        global CURRENT_LANG
        self.setWindowTitle(tr('app_title'))
        self.setGeometry(100, 100, 900, 700)
        self.config = load_config()
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        # Thêm layout ngang cho language switch ở góc phải
        top_layout = QHBoxLayout()
        top_layout.addStretch(1)
        self.lang_label = QLabel(tr('language'))
        self.lang_combo = QComboBox()
        self.lang_combo.addItems(['Tiếng Việt', 'English'])
        self.lang_combo.setCurrentIndex(0 if CURRENT_LANG == 'vi' else 1)
        self.lang_combo.currentIndexChanged.connect(self.change_language)
        top_layout.addWidget(self.lang_label)
        top_layout.addWidget(self.lang_combo)
        layout.addLayout(top_layout)
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)
        self.edge_tab = QWidget()
        self.setup_edge_tab()
        self.tab_widget.addTab(self.edge_tab, tr('edge_tab'))
        self.gemini_tab = QWidget()
        self.setup_gemini_tab()
        self.tab_widget.addTab(self.gemini_tab, tr('gemini_tab'))
        self.google_tab = QWidget()
        self.setup_google_tab()
        self.tab_widget.addTab(self.google_tab, tr('google_tab'))
        self.openai_tab = QWidget()
        self.setup_openai_tab()
        self.tab_widget.addTab(self.openai_tab, tr('openai_tab'))

    def change_language(self, idx):
        global CURRENT_LANG
        CURRENT_LANG = 'vi' if idx == 0 else 'en'
        self.setWindowTitle(tr('app_title'))
        self.lang_label.setText(tr('language'))
        # Xóa toàn bộ tab cũ
        self.tab_widget.clear()
        # Tạo lại từng tab mới hoàn toàn
        self.edge_tab = QWidget()
        self.setup_edge_tab()
        self.tab_widget.addTab(self.edge_tab, tr('edge_tab'))
        self.gemini_tab = QWidget()
        self.setup_gemini_tab()
        self.tab_widget.addTab(self.gemini_tab, tr('gemini_tab'))
        self.google_tab = QWidget()
        self.setup_google_tab()
        self.tab_widget.addTab(self.google_tab, tr('google_tab'))
        self.openai_tab = QWidget()
        self.setup_openai_tab()
        self.tab_widget.addTab(self.openai_tab, tr('openai_tab'))

    def setup_edge_tab(self):
        layout = QVBoxLayout()
        self.edge_text = QTextEdit()
        self.edge_text.setPlaceholderText(tr('input_placeholder'))
        layout.addWidget(self.edge_text)
        voice_layout = QHBoxLayout()
        voice_label = QLabel(tr('choose_voice'))
        self.edge_voice_combo = QComboBox()
        self.edge_voice_combo.addItems([
            "vi-VN-HoaiMyNeural",  # Nữ
            "vi-VN-NamMinhNeural"  # Nam
        ])
        voice_layout.addWidget(voice_label)
        voice_layout.addWidget(self.edge_voice_combo)
        layout.addLayout(voice_layout)
        button_layout = QHBoxLayout()
        self.edge_convert_btn = QPushButton(tr('convert_btn'))
        self.edge_convert_btn.clicked.connect(self.convert_edge_tts)
        button_layout.addWidget(self.edge_convert_btn)
        self.edge_save_btn = QPushButton(tr('save_btn'))
        self.edge_save_btn.clicked.connect(self.save_edge_audio)
        button_layout.addWidget(self.edge_save_btn)
        layout.addLayout(button_layout)
        self.edge_status = QLabel("")
        layout.addWidget(self.edge_status)
        self.edge_tab.setLayout(layout)
        self.edge_audio_file = None
        self.edge_thread = None

    def convert_edge_tts(self):
        text = self.edge_text.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, tr('status_error'), tr('warning_no_text'))
            return
        voice = self.edge_voice_combo.currentText()
        self.edge_audio_file = "edge_tts.mp3"
        self.edge_convert_btn.setEnabled(False)
        self.edge_status.setText(tr('status_converting'))
        self.edge_thread = TTSThread(text, voice, self.edge_audio_file)
        self.edge_thread.finished.connect(self.on_edge_finished)
        self.edge_thread.error.connect(self.on_edge_error)
        self.edge_thread.start()

    def on_edge_finished(self):
        self.edge_convert_btn.setEnabled(True)
        self.edge_status.setText(tr('status_success'))
        os.system(f'start {self.edge_audio_file}')

    def on_edge_error(self, error_msg):
        self.edge_convert_btn.setEnabled(True)
        self.edge_status.setText(f"{tr('status_error')}: {error_msg}")
        QMessageBox.critical(self, tr('status_error'), f"{tr('status_error')}: {error_msg}")

    def save_edge_audio(self):
        if not self.edge_audio_file or not os.path.exists(self.edge_audio_file):
            QMessageBox.warning(self, tr('status_error'), tr('warning_no_text'))
            return
        file_name, _ = QFileDialog.getSaveFileName(self, tr('save_btn'), "", "Audio Files (*.mp3)")
        if file_name:
            try:
                import shutil
                shutil.copy2(self.edge_audio_file, file_name)
                QMessageBox.information(self, tr('status_success'), tr('status_success'))
            except Exception as e:
                QMessageBox.critical(self, tr('status_error'), f"{tr('status_error')}: {str(e)}")

    def setup_gemini_tab(self):
        layout = QVBoxLayout()
        api_layout = QHBoxLayout()
        api_label = QLabel(tr('gemini_api_key'))
        self.gemini_api_key_edit = QLineEdit()
        self.gemini_api_key_edit.setPlaceholderText(tr('warning_no_key'))
        if self.config.get("gemini_api_key"):
            self.gemini_api_key_edit.setText(self.config["gemini_api_key"])
        self.gemini_api_key_edit.textChanged.connect(self.save_gemini_api_key)
        api_layout.addWidget(api_label)
        api_layout.addWidget(self.gemini_api_key_edit)
        layout.addLayout(api_layout)
        self.gemini_text = QTextEdit()
        self.gemini_text.setPlaceholderText(tr('input_placeholder'))
        layout.addWidget(self.gemini_text)
        voice_layout = QHBoxLayout()
        voice_label = QLabel(tr('choose_voice'))
        self.gemini_voice_combo = QComboBox()
        # Danh sách voice phổ biến từ tài liệu Gemini
        voices = [
            "Kore", "Zephyr", "Puck", "Charon", "Fenrir", "Leda", "Orus", "Aoede", "Callirrhoe", "Autonoe", "Enceladus", "Iapetus", "Umbriel", "Algieba", "Despina", "Erinome", "Algenib", "Rasalgethi", "Laomedeia", "Achernar", "Alnilam", "Schedar", "Gacrux", "Pulcherrima", "Achird", "Zubenelgenubi", "Vindemiatrix", "Sadachbia", "Sadaltager", "Sulafat"
        ]
        self.gemini_voice_combo.addItems(voices)
        voice_layout.addWidget(voice_label)
        voice_layout.addWidget(self.gemini_voice_combo)
        layout.addLayout(voice_layout)
        button_layout = QHBoxLayout()
        self.gemini_convert_btn = QPushButton(tr('convert_btn'))
        self.gemini_convert_btn.clicked.connect(self.convert_gemini_tts)
        button_layout.addWidget(self.gemini_convert_btn)
        self.gemini_save_btn = QPushButton(tr('save_btn'))
        self.gemini_save_btn.clicked.connect(self.save_gemini_audio)
        button_layout.addWidget(self.gemini_save_btn)
        layout.addLayout(button_layout)
        self.gemini_status = QLabel("")
        layout.addWidget(self.gemini_status)
        self.gemini_tab.setLayout(layout)
        self.gemini_audio_file = None

    def convert_gemini_tts(self):
        api_key = self.gemini_api_key_edit.text().strip()
        text = self.gemini_text.toPlainText().strip()
        voice_name = self.gemini_voice_combo.currentText()
        if not api_key:
            QMessageBox.warning(self, tr('status_error'), tr('warning_no_key'))
            return
        if not text:
            QMessageBox.warning(self, tr('status_error'), tr('warning_no_text'))
            return
        self.gemini_audio_file = "gemini_tts.wav"
        self.gemini_convert_btn.setEnabled(False)
        self.gemini_status.setText(tr('status_converting'))
        try:
            from google import genai
            from google.genai import types
            import wave
            def wave_file(filename, pcm, channels=1, rate=24000, sample_width=2):
                with wave.open(filename, "wb") as wf:
                    wf.setnchannels(channels)
                    wf.setsampwidth(sample_width)
                    wf.setframerate(rate)
                    wf.writeframes(pcm)
            client = genai.Client(api_key=api_key)
            # Phát hiện multi-speaker nếu có nhiều dòng dạng "Tên: ..."
            import re
            speaker_lines = re.findall(r"^(.*?):", text, re.MULTILINE)
            speakers = list(dict.fromkeys([s.strip() for s in speaker_lines if s.strip()]))
            if len(speakers) >= 2:
                # Gán voice mặc định cho từng speaker (luân phiên Kore, Puck)
                voice_map = {}
                default_voices = ["Kore", "Puck", "Zephyr", "Charon"]
                for idx, spk in enumerate(speakers):
                    voice_map[spk] = default_voices[idx % len(default_voices)]
                speaker_voice_configs = [
                    types.SpeakerVoiceConfig(
                        speaker=spk,
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name=voice_map[spk],
                            )
                        )
                    ) for spk in speakers
                ]
                response = client.models.generate_content(
                    model="gemini-2.5-flash-preview-tts",
                    contents=text,
                    config=types.GenerateContentConfig(
                        response_modalities=["AUDIO"],
                        speech_config=types.SpeechConfig(
                            multi_speaker_voice_config=types.MultiSpeakerVoiceConfig(
                                speaker_voice_configs=speaker_voice_configs
                            )
                        ),
                    )
                )
            else:
                # Single speaker
                response = client.models.generate_content(
                    model="gemini-2.5-flash-preview-tts",
                    contents=text,
                    config=types.GenerateContentConfig(
                        response_modalities=["AUDIO"],
                        speech_config=types.SpeechConfig(
                            voice_config=types.VoiceConfig(
                                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                    voice_name=voice_name,
                                )
                            )
                        ),
                    )
                )
            # Kiểm tra response hợp lệ
            if not response or not response.candidates or not response.candidates[0].content or not hasattr(response.candidates[0].content, "parts") or not response.candidates[0].content.parts:
                self.gemini_status.setText("Không nhận được dữ liệu âm thanh từ Gemini API. Có thể API key không hợp lệ, hết quota, hoặc voice/model không hỗ trợ.")
                QMessageBox.critical(self, tr('status_error'), "Không nhận được dữ liệu âm thanh từ Gemini API. Có thể API key không hợp lệ, hết quota, hoặc voice/model không hỗ trợ.")
            else:
                data = response.candidates[0].content.parts[0].inline_data.data
                wave_file(self.gemini_audio_file, data)
                self.gemini_status.setText(tr('status_success'))
                os.system(f'start {self.gemini_audio_file}')
        except Exception as e:
            self.gemini_status.setText(f"{tr('status_error')}: {e}")
            QMessageBox.critical(self, tr('status_error'), f"{tr('status_error')}: {e}")
        self.gemini_convert_btn.setEnabled(True)

    def save_gemini_audio(self):
        if not self.gemini_audio_file or not os.path.exists(self.gemini_audio_file):
            QMessageBox.warning(self, tr('status_error'), tr('warning_no_text'))
            return
        file_name, _ = QFileDialog.getSaveFileName(self, tr('save_btn'), "", "Audio Files (*.wav)")
        if file_name:
            try:
                import shutil
                shutil.copy2(self.gemini_audio_file, file_name)
                QMessageBox.information(self, tr('status_success'), tr('status_success'))
            except Exception as e:
                QMessageBox.critical(self, tr('status_error'), f"{tr('status_error')}: {str(e)}")

    def save_gemini_api_key(self):
        self.config["gemini_api_key"] = self.gemini_api_key_edit.text().strip()
        save_config(self.config)

    def setup_google_tab(self):
        layout = QVBoxLayout()
        self.google_text = QTextEdit()
        self.google_text.setPlaceholderText(tr('input_placeholder'))
        layout.addWidget(self.google_text)
        voice_layout = QHBoxLayout()
        voice_label = QLabel(tr('choose_voice'))
        self.google_voice_combo = QComboBox()
        for v_id, v_label in VIETNAMESE_VOICES:
            self.google_voice_combo.addItem(v_label, v_id)
        voice_layout.addWidget(voice_label)
        voice_layout.addWidget(self.google_voice_combo)
        layout.addLayout(voice_layout)
        key_layout = QHBoxLayout()
        self.google_key_label = QLabel(tr('no_json'))
        self.google_key_btn = QPushButton(tr('choose_json_btn'))
        self.google_key_btn.clicked.connect(self.choose_google_json_key)
        key_layout.addWidget(self.google_key_btn)
        key_layout.addWidget(self.google_key_label)
        layout.addLayout(key_layout)
        self.google_json_key_path = self.config.get("google_json_key_path", None)
        if self.google_json_key_path and os.path.exists(self.google_json_key_path):
            self.google_key_label.setText(os.path.basename(self.google_json_key_path))
        else:
            self.google_json_key_path = None
        button_layout = QHBoxLayout()
        self.google_convert_btn = QPushButton(tr('convert_btn'))
        self.google_convert_btn.clicked.connect(self.convert_google_tts)
        button_layout.addWidget(self.google_convert_btn)
        self.google_save_btn = QPushButton(tr('save_btn'))
        self.google_save_btn.clicked.connect(self.save_google_audio)
        button_layout.addWidget(self.google_save_btn)
        layout.addLayout(button_layout)
        self.google_status = QLabel("")
        layout.addWidget(self.google_status)
        self.google_tab.setLayout(layout)
        self.google_audio_file = None

    def choose_google_json_key(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Chọn file JSON key Google Cloud", "", "JSON Files (*.json)")
        if file_path:
            self.google_key_label.setText(os.path.basename(file_path))
            self.google_json_key_path = file_path
            self.config["google_json_key_path"] = file_path
            save_config(self.config)
        else:
            self.google_key_label.setText(tr('no_json'))
            self.google_json_key_path = None
            self.config["google_json_key_path"] = ""
            save_config(self.config)

    def convert_google_tts(self):
        text = self.google_text.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, tr('status_error'), tr('warning_no_text'))
            return
        if not self.google_json_key_path or not os.path.exists(self.google_json_key_path):
            QMessageBox.warning(self, tr('status_error'), tr('warning_no_json'))
            return
        voice = self.google_voice_combo.currentData()
        self.google_audio_file = "google_tts.mp3"
        self.google_convert_btn.setEnabled(False)
        self.google_status.setText(tr('status_converting'))
        try:
            client = texttospeech.TextToSpeechClient.from_service_account_file(self.google_json_key_path)
            synthesis_input = texttospeech.SynthesisInput(text=text)
            voice_params = texttospeech.VoiceSelectionParams(
                language_code="vi-VN",
                name=voice
            )
            audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3)
            response = client.synthesize_speech(
                input=synthesis_input,
                voice=voice_params,
                audio_config=audio_config
            )
            with open(self.google_audio_file, "wb") as out:
                out.write(response.audio_content)
            self.google_status.setText(tr('status_success'))
            os.system(f'start {self.google_audio_file}')
        except Exception as e:
            self.google_status.setText(f"{tr('status_error')}: {e}")
            QMessageBox.critical(self, tr('status_error'), f"{tr('status_error')}: {e}")
        self.google_convert_btn.setEnabled(True)

    def save_google_audio(self):
        if not self.google_audio_file or not os.path.exists(self.google_audio_file):
            QMessageBox.warning(self, tr('status_error'), tr('warning_no_text'))
            return
        file_name, _ = QFileDialog.getSaveFileName(self, tr('save_btn'), "", "Audio Files (*.mp3)")
        if file_name:
            try:
                import shutil
                shutil.copy2(self.google_audio_file, file_name)
                QMessageBox.information(self, tr('status_success'), tr('status_success'))
            except Exception as e:
                QMessageBox.critical(self, tr('status_error'), f"{tr('status_error')}: {str(e)}")

    def setup_openai_tab(self):
        layout = QVBoxLayout()
        api_layout = QHBoxLayout()
        api_label = QLabel(tr('openai_api_key'))
        self.openai_api_key_edit = QLineEdit()
        api_layout.addWidget(api_label)
        api_layout.addWidget(self.openai_api_key_edit)
        layout.addLayout(api_layout)
        self.openai_text = QTextEdit()
        self.openai_text.setPlaceholderText(tr('input_placeholder'))
        layout.addWidget(self.openai_text)
        voice_layout = QHBoxLayout()
        voice_label = QLabel(tr('choose_voice'))
        self.openai_voice_combo = QComboBox()
        self.openai_voice_combo.addItems(["onyx", "nova", "shimmer", "echo", "fable", "alloy", "coral"])
        voice_layout.addWidget(voice_label)
        voice_layout.addWidget(self.openai_voice_combo)
        layout.addLayout(voice_layout)
        button_layout = QHBoxLayout()
        self.openai_convert_btn = QPushButton(tr('convert_btn'))
        # self.openai_convert_btn.clicked.connect(self.convert_openai_tts)  # TODO: Thêm xử lý sau
        button_layout.addWidget(self.openai_convert_btn)
        self.openai_save_btn = QPushButton(tr('save_btn'))
        # self.openai_save_btn.clicked.connect(self.save_openai_audio)  # TODO: Thêm xử lý sau
        button_layout.addWidget(self.openai_save_btn)
        layout.addLayout(button_layout)
        self.openai_status = QLabel("")
        layout.addWidget(self.openai_status)
        self.openai_tab.setLayout(layout)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = TextToSpeechApp()
    window.show()
    sys.exit(app.exec_()) 