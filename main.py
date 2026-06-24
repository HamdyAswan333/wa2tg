"""
WA2TG - WhatsApp to Telegram Transfer App
تطبيق نقل محادثات واتساب إلى تيليجرام
"""

import os
import re
import time
import threading
import requests
from datetime import datetime
from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen, SlideTransition
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.progressbar import ProgressBar
from kivy.uix.popup import Popup
from kivy.uix.filechooser import FileChooserListView
from kivy.core.window import Window
from kivy.utils import get_color_from_hex
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.widget import Widget
from kivy.graphics import Color, RoundedRectangle

# ألوان التطبيق
COLOR_WA = "#075E54"
COLOR_WA_LIGHT = "#25D366"
COLOR_TG = "#229ED9"
COLOR_TG_DARK = "#1565C0"
COLOR_BG = "#F0F2F5"
COLOR_WHITE = "#FFFFFF"
COLOR_TEXT = "#1A1A2E"
COLOR_GRAY = "#888888"
COLOR_ERROR = "#E53935"
COLOR_SUCCESS = "#43A047"

Window.clearcolor = get_color_from_hex(COLOR_BG + "FF")


def parse_whatsapp_chat(file_path):
    """تحليل ملف تصدير واتساب واستخراج الرسائل"""
    messages = []
    
    # أنماط التواريخ المختلفة في واتساب
    patterns = [
        r'(\d{1,2}/\d{1,2}/\d{2,4},\s*\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM|ص|م)?)\s*-\s*([^:]+):\s*(.*)',
        r'\[(\d{1,2}/\d{1,2}/\d{2,4},\s*\d{1,2}:\d{2}(?::\d{2})?)\]\s*([^:]+):\s*(.*)',
        r'(\d{1,2}\.\d{1,2}\.\d{2,4},\s*\d{1,2}:\d{2})\s*-\s*([^:]+):\s*(.*)',
    ]
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            content = f.read()
    
    lines = content.split('\n')
    current_msg = None
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        matched = False
        for pattern in patterns:
            match = re.match(pattern, line)
            if match:
                if current_msg:
                    messages.append(current_msg)
                
                date_str, sender, text = match.groups()
                sender = sender.strip()
                text = text.strip()
                
                # تجاهل رسائل النظام
                if any(x in text for x in ['<Media omitted>', 'image omitted', 'video omitted', 
                                             'audio omitted', 'document omitted', 'صورة', 'فيديو',
                                             'تم حذف هذه الرسالة', 'This message was deleted']):
                    current_msg = None
                    matched = True
                    break
                
                current_msg = {
                    'date': date_str.strip(),
                    'sender': sender,
                    'text': text
                }
                matched = True
                break
        
        if not matched and current_msg:
            # رسالة متعددة الأسطر
            current_msg['text'] += '\n' + line
    
    if current_msg:
        messages.append(current_msg)
    
    return messages


def send_to_telegram(token, chat_id, messages, progress_callback, batch_size=20, delay=0.5):
    """إرسال الرسائل لتيليجرام مع التحكم في السرعة"""
    base_url = f"https://api.telegram.org/bot{token}"
    
    # التحقق من صحة البوت
    try:
        resp = requests.get(f"{base_url}/getMe", timeout=10)
        if not resp.json().get('ok'):
            return False, "❌ التوكن غلط، تحقق منه"
    except Exception as e:
        return False, f"❌ فشل الاتصال: {str(e)}"
    
    total = len(messages)
    sent = 0
    failed = 0
    
    # إرسال رسالة ترحيب
    header = f"📦 *بداية نقل المحادثة*\n📊 إجمالي الرسائل: {total}\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    requests.post(f"{base_url}/sendMessage", json={
        'chat_id': chat_id,
        'text': header,
        'parse_mode': 'Markdown'
    }, timeout=10)
    
    time.sleep(1)
    
    # إرسال الرسائل على دفعات
    batch_text = ""
    batch_count = 0
    
    for i, msg in enumerate(messages):
        line = f"*{msg['sender']}* [{msg['date']}]\n{msg['text']}\n\n"
        batch_text += line
        batch_count += 1
        
        if batch_count >= batch_size or i == total - 1:
            try:
                # تقسيم إذا تجاوز حد تيليجرام (4096 حرف)
                chunks = [batch_text[j:j+4000] for j in range(0, len(batch_text), 4000)]
                for chunk in chunks:
                    requests.post(f"{base_url}/sendMessage", json={
                        'chat_id': chat_id,
                        'text': chunk,
                        'parse_mode': 'Markdown'
                    }, timeout=15)
                    time.sleep(delay)
                
                sent += batch_count
                progress_callback(sent, total)
                
            except Exception as e:
                failed += batch_count
            
            batch_text = ""
            batch_count = 0
            time.sleep(delay)
    
    # رسالة ختامية
    footer = f"✅ *اكتمل النقل*\n📨 تم إرسال: {sent}\n❌ فشل: {failed}"
    requests.post(f"{base_url}/sendMessage", json={
        'chat_id': chat_id,
        'text': footer,
        'parse_mode': 'Markdown'
    }, timeout=10)
    
    return True, f"تم إرسال {sent} رسالة بنجاح"


# ======= الشاشات =======

class CardWidget(BoxLayout):
    def __init__(self, bg_color=COLOR_WHITE, radius=16, **kwargs):
        super().__init__(**kwargs)
        self.bg_color = bg_color
        self.radius = radius
        with self.canvas.before:
            Color(*get_color_from_hex(bg_color + "FF"))
            self.rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(radius)])
        self.bind(pos=self._update, size=self._update)
    
    def _update(self, *args):
        self.rect.pos = self.pos
        self.rect.size = self.size


def make_button(text, bg=COLOR_TG, fg=COLOR_WHITE, height=50, radius=14, font_size=16):
    btn = Button(
        text=text,
        size_hint_y=None,
        height=dp(height),
        background_normal='',
        background_color=get_color_from_hex(bg + "FF"),
        color=get_color_from_hex(fg + "FF"),
        font_size=dp(font_size),
        bold=True,
    )
    return btn


def make_label(text, size=14, color=COLOR_TEXT, bold=False, halign='right'):
    lbl = Label(
        text=text,
        font_size=dp(size),
        color=get_color_from_hex(color + "FF"),
        bold=bold,
        halign=halign,
        valign='middle',
        size_hint_y=None,
        height=dp(30),
        text_size=(None, None),
    )
    lbl.bind(size=lambda inst, val: setattr(inst, 'text_size', (val[0], None)))
    return lbl


def make_input(hint, multiline=False, password=False, height=48):
    inp = TextInput(
        hint_text=hint,
        multiline=multiline,
        password=password,
        size_hint_y=None,
        height=dp(height),
        font_size=dp(15),
        padding=[dp(12), dp(12)],
        background_color=get_color_from_hex("#F8F9FA" + "FF"),
        foreground_color=get_color_from_hex(COLOR_TEXT + "FF"),
        hint_text_color=get_color_from_hex(COLOR_GRAY + "FF"),
        cursor_color=get_color_from_hex(COLOR_TG + "FF"),
    )
    return inp


class HomeScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.build_ui()
    
    def build_ui(self):
        root = BoxLayout(orientation='vertical', padding=dp(20), spacing=dp(15))
        
        # هيدر
        header = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(140), spacing=dp(8))
        
        logo = Label(
            text="💬➡️✈️",
            font_size=dp(52),
            size_hint_y=None,
            height=dp(70),
        )
        
        title = Label(
            text="WA2TG",
            font_size=dp(28),
            bold=True,
            color=get_color_from_hex(COLOR_WA + "FF"),
            size_hint_y=None,
            height=dp(36),
        )
        
        subtitle = Label(
            text="نقل محادثات واتساب إلى تيليجرام",
            font_size=dp(13),
            color=get_color_from_hex(COLOR_GRAY + "FF"),
            size_hint_y=None,
            height=dp(24),
        )
        
        header.add_widget(logo)
        header.add_widget(title)
        header.add_widget(subtitle)
        
        # بطاقة الخطوات
        steps_card = CardWidget(orientation='vertical', padding=dp(16), spacing=dp(10),
                                 size_hint_y=None, height=dp(200))
        
        steps_title = make_label("📋 طريقة الاستخدام", size=15, bold=True, color=COLOR_WA)
        steps_card.add_widget(steps_title)
        
        steps = [
            "1️⃣  افتح واتساب ← المحادثة ← ⋮ ← تصدير الدردشة",
            "2️⃣  احفظ ملف الـ .txt على هاتفك",
            "3️⃣  حط توكن البوت و Chat ID في التطبيق",
            "4️⃣  اختار الملف واضغط إرسال ✅",
        ]
        
        for step in steps:
            lbl = make_label(step, size=12, color=COLOR_TEXT)
            lbl.height = dp(28)
            steps_card.add_widget(lbl)
        
        # أزرار
        btn_single = make_button("📂  نقل محادثة واحدة", bg=COLOR_WA)
        btn_single.bind(on_press=lambda x: setattr(self.manager, 'current', 'setup'))
        
        btn_multi = make_button("📁  نقل عدة محادثات", bg=COLOR_TG)
        btn_multi.bind(on_press=lambda x: setattr(self.manager, 'current', 'multi'))
        
        root.add_widget(header)
        root.add_widget(steps_card)
        root.add_widget(Widget())  # spacer
        root.add_widget(btn_single)
        root.add_widget(btn_multi)
        root.add_widget(make_label("v1.0 — تطبيق خاص", size=11, color=COLOR_GRAY, halign='center'))
        
        self.add_widget(root)


class SetupScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.selected_file = None
        self.build_ui()
    
    def build_ui(self):
        scroll = ScrollView()
        root = BoxLayout(orientation='vertical', padding=dp(20), spacing=dp(12),
                         size_hint_y=None)
        root.bind(minimum_height=root.setter('height'))
        
        # هيدر
        header = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(10))
        back_btn = Button(text="←", size_hint_x=None, width=dp(44),
                          background_normal='', background_color=get_color_from_hex(COLOR_WA+"FF"),
                          color=(1,1,1,1), font_size=dp(20), bold=True)
        back_btn.bind(on_press=lambda x: setattr(self.manager, 'current', 'home'))
        
        title = make_label("إعداد النقل", size=18, bold=True, color=COLOR_WA, halign='right')
        title.height = dp(50)
        
        header.add_widget(back_btn)
        header.add_widget(title)
        
        # توكن البوت
        root.add_widget(make_label("🤖 Telegram Bot Token", size=14, bold=True, color=COLOR_TG))
        self.token_input = make_input("110201543:AAHdqTcvCHZvKjH9jX39...")
        root.add_widget(self.token_input)
        
        help_token = make_label("احصل عليه من @BotFather في تيليجرام", size=11, color=COLOR_GRAY)
        root.add_widget(help_token)
        
        # Chat ID
        root.add_widget(make_label("💬 Chat ID أو Username", size=14, bold=True, color=COLOR_TG))
        self.chatid_input = make_input("مثال: -1001234567890 أو @channel_name")
        root.add_widget(self.chatid_input)
        
        help_chatid = make_label("ابعت رسالة للبوت ثم اتصفح api.telegram.org/bot{TOKEN}/getUpdates", size=11, color=COLOR_GRAY)
        help_chatid.height = dp(40)
        root.add_widget(help_chatid)
        
        # حجم الدفعة
        root.add_widget(make_label("📦 عدد الرسائل في كل دفعة (1-50)", size=14, bold=True, color=COLOR_TG))
        self.batch_input = make_input("20")
        self.batch_input.text = "20"
        root.add_widget(self.batch_input)
        
        # اختيار الملف
        root.add_widget(make_label("📄 ملف واتساب (.txt)", size=14, bold=True, color=COLOR_WA))
        
        self.file_btn = make_button("📂  اختار الملف", bg=COLOR_WA, height=48)
        self.file_btn.bind(on_press=self.open_file_chooser)
        root.add_widget(self.file_btn)
        
        self.file_label = make_label("لم يتم اختيار ملف", size=12, color=COLOR_GRAY, halign='center')
        root.add_widget(self.file_label)
        
        root.add_widget(Widget(size_hint_y=None, height=dp(10)))
        
        # زر الإرسال
        send_btn = make_button("🚀  ابدأ الإرسال", bg=COLOR_TG, height=54, font_size=18)
        send_btn.bind(on_press=self.start_transfer)
        root.add_widget(send_btn)
        
        header_container = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(60), padding=[0, dp(5)])
        header_container.add_widget(header)
        
        main = BoxLayout(orientation='vertical', padding=dp(20), spacing=dp(12))
        main.add_widget(header_container)
        main.add_widget(scroll)
        
        scroll.add_widget(root)
        self.add_widget(main)
    
    def open_file_chooser(self, *args):
        content = BoxLayout(orientation='vertical', spacing=dp(10))
        
        fc = FileChooserListView(
            filters=['*.txt', '*.zip'],
            path=os.path.expanduser('~'),
        )
        
        btn_layout = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(10))
        
        select_btn = make_button("✅ اختار", bg=COLOR_WA, height=44)
        cancel_btn = make_button("❌ إلغاء", bg=COLOR_ERROR, height=44)
        
        btn_layout.add_widget(select_btn)
        btn_layout.add_widget(cancel_btn)
        
        content.add_widget(fc)
        content.add_widget(btn_layout)
        
        popup = Popup(title="اختار ملف الواتساب", content=content, size_hint=(0.95, 0.85))
        
        def on_select(*args):
            if fc.selection:
                self.selected_file = fc.selection[0]
                fname = os.path.basename(self.selected_file)
                self.file_label.text = f"✅ {fname}"
                self.file_label.color = get_color_from_hex(COLOR_SUCCESS + "FF")
                self.file_btn.text = f"📄 {fname[:30]}..."
            popup.dismiss()
        
        select_btn.bind(on_press=on_select)
        cancel_btn.bind(on_press=popup.dismiss)
        popup.open()
    
    def start_transfer(self, *args):
        token = self.token_input.text.strip()
        chat_id = self.chatid_input.text.strip()
        
        if not token:
            self.show_error("❌ حط التوكن الأول!")
            return
        if not chat_id:
            self.show_error("❌ حط الـ Chat ID!")
            return
        if not self.selected_file:
            self.show_error("❌ اختار ملف واتساب!")
            return
        
        try:
            batch = int(self.batch_input.text or "20")
            batch = max(1, min(50, batch))
        except:
            batch = 20
        
        # انتقل لشاشة التقدم
        progress_screen = self.manager.get_screen('progress')
        progress_screen.set_params(token, chat_id, self.selected_file, batch)
        self.manager.current = 'progress'
    
    def show_error(self, msg):
        popup = Popup(
            title="خطأ",
            content=Label(text=msg, font_size=dp(15)),
            size_hint=(0.8, 0.3)
        )
        popup.open()


class MultiScreen(Screen):
    """شاشة نقل عدة محادثات"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.files = []
        self.build_ui()
    
    def build_ui(self):
        root = BoxLayout(orientation='vertical', padding=dp(20), spacing=dp(12))
        
        # هيدر
        header = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(10))
        back_btn = Button(text="←", size_hint_x=None, width=dp(44),
                          background_normal='', background_color=get_color_from_hex(COLOR_TG+"FF"),
                          color=(1,1,1,1), font_size=dp(20), bold=True)
        back_btn.bind(on_press=lambda x: setattr(self.manager, 'current', 'home'))
        title = make_label("نقل عدة محادثات", size=18, bold=True, color=COLOR_TG, halign='right')
        title.height = dp(50)
        header.add_widget(back_btn)
        header.add_widget(title)
        root.add_widget(header)
        
        root.add_widget(make_label("🤖 Bot Token", size=14, bold=True, color=COLOR_TG))
        self.token_input = make_input("Bot Token من @BotFather")
        root.add_widget(self.token_input)
        
        root.add_widget(make_label("💬 Chat ID", size=14, bold=True, color=COLOR_TG))
        self.chatid_input = make_input("Chat ID أو @username")
        root.add_widget(self.chatid_input)
        
        root.add_widget(make_label("📁 الملفات المختارة", size=14, bold=True, color=COLOR_WA))
        
        add_btn = make_button("➕  أضف ملف محادثة", bg=COLOR_WA, height=46)
        add_btn.bind(on_press=self.add_file)
        root.add_widget(add_btn)
        
        self.files_scroll = ScrollView(size_hint_y=None, height=dp(150))
        self.files_list = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(4))
        self.files_list.bind(minimum_height=self.files_list.setter('height'))
        self.files_scroll.add_widget(self.files_list)
        root.add_widget(self.files_scroll)
        
        self.count_label = make_label("لم تتم إضافة ملفات بعد", size=12, color=COLOR_GRAY, halign='center')
        root.add_widget(self.count_label)
        
        root.add_widget(Widget())
        
        send_btn = make_button("🚀  إرسال كل المحادثات", bg=COLOR_TG, height=54, font_size=17)
        send_btn.bind(on_press=self.start_multi_transfer)
        root.add_widget(send_btn)
        
        self.add_widget(root)
    
    def add_file(self, *args):
        content = BoxLayout(orientation='vertical', spacing=dp(10))
        fc = FileChooserListView(filters=['*.txt'], path=os.path.expanduser('~'))
        btn_layout = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(10))
        select_btn = make_button("✅ اختار", bg=COLOR_WA, height=44)
        cancel_btn = make_button("❌ إلغاء", bg=COLOR_ERROR, height=44)
        btn_layout.add_widget(select_btn)
        btn_layout.add_widget(cancel_btn)
        content.add_widget(fc)
        content.add_widget(btn_layout)
        popup = Popup(title="اختار ملف", content=content, size_hint=(0.95, 0.85))
        
        def on_select(*args):
            if fc.selection:
                fpath = fc.selection[0]
                if fpath not in self.files:
                    self.files.append(fpath)
                    self.update_files_list()
            popup.dismiss()
        
        select_btn.bind(on_press=on_select)
        cancel_btn.bind(on_press=popup.dismiss)
        popup.open()
    
    def update_files_list(self):
        self.files_list.clear_widgets()
        for i, f in enumerate(self.files):
            row = BoxLayout(size_hint_y=None, height=dp(36), spacing=dp(8))
            lbl = Label(text=f"📄 {os.path.basename(f)}", font_size=dp(12),
                       color=get_color_from_hex(COLOR_TEXT+"FF"), halign='right')
            del_btn = Button(text="✕", size_hint_x=None, width=dp(32),
                           background_normal='', background_color=get_color_from_hex(COLOR_ERROR+"FF"),
                           color=(1,1,1,1), font_size=dp(13))
            idx = i
            del_btn.bind(on_press=lambda x, i=idx: self.remove_file(i))
            row.add_widget(lbl)
            row.add_widget(del_btn)
            self.files_list.add_widget(row)
        
        count = len(self.files)
        self.count_label.text = f"✅ {count} محادثة جاهزة للإرسال" if count > 0 else "لم تتم إضافة ملفات بعد"
        self.count_label.color = get_color_from_hex((COLOR_SUCCESS if count > 0 else COLOR_GRAY) + "FF")
    
    def remove_file(self, idx):
        if 0 <= idx < len(self.files):
            self.files.pop(idx)
            self.update_files_list()
    
    def start_multi_transfer(self, *args):
        if not self.token_input.text.strip():
            return
        if not self.chatid_input.text.strip():
            return
        if not self.files:
            return
        
        progress_screen = self.manager.get_screen('progress')
        progress_screen.set_params(
            self.token_input.text.strip(),
            self.chatid_input.text.strip(),
            self.files[0],  # سيتم دعم عدة ملفات في الإصدار القادم
            20,
            multi_files=self.files
        )
        self.manager.current = 'progress'


class ProgressScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.token = ""
        self.chat_id = ""
        self.file_path = ""
        self.batch_size = 20
        self.multi_files = None
        self.build_ui()
    
    def build_ui(self):
        root = BoxLayout(orientation='vertical', padding=dp(24), spacing=dp(16),
                        background_color=(1,1,1,1))
        
        self.status_emoji = Label(text="⏳", font_size=dp(60), size_hint_y=None, height=dp(80))
        root.add_widget(self.status_emoji)
        
        self.title_label = Label(
            text="جاري الإرسال...",
            font_size=dp(20), bold=True,
            color=get_color_from_hex(COLOR_TG + "FF"),
            size_hint_y=None, height=dp(36)
        )
        root.add_widget(self.title_label)
        
        self.progress = ProgressBar(max=100, value=0, size_hint_y=None, height=dp(20))
        root.add_widget(self.progress)
        
        self.count_label = Label(
            text="0 / 0 رسالة",
            font_size=dp(16),
            color=get_color_from_hex(COLOR_GRAY + "FF"),
            size_hint_y=None, height=dp(30)
        )
        root.add_widget(self.count_label)
        
        self.log_scroll = ScrollView()
        self.log_label = Label(
            text="",
            font_size=dp(12),
            color=get_color_from_hex(COLOR_TEXT + "FF"),
            halign='right',
            valign='top',
            size_hint_y=None,
            text_size=(Window.width - dp(48), None)
        )
        self.log_label.bind(texture_size=self.log_label.setter('size'))
        self.log_scroll.add_widget(self.log_label)
        root.add_widget(self.log_scroll)
        
        root.add_widget(Widget())
        
        self.done_btn = make_button("🏠  العودة للرئيسية", bg=COLOR_WA, height=50)
        self.done_btn.bind(on_press=lambda x: setattr(self.manager, 'current', 'home'))
        self.done_btn.opacity = 0
        self.done_btn.disabled = True
        root.add_widget(self.done_btn)
        
        self.add_widget(root)
    
    def set_params(self, token, chat_id, file_path, batch_size=20, multi_files=None):
        self.token = token
        self.chat_id = chat_id
        self.file_path = file_path
        self.batch_size = batch_size
        self.multi_files = multi_files
        self.reset_ui()
    
    def reset_ui(self):
        self.progress.value = 0
        self.count_label.text = "0 / 0 رسالة"
        self.title_label.text = "جاري الإرسال..."
        self.status_emoji.text = "⏳"
        self.log_label.text = ""
        self.done_btn.opacity = 0
        self.done_btn.disabled = True
    
    def on_enter(self):
        Clock.schedule_once(lambda dt: self.start_transfer(), 0.5)
    
    def start_transfer(self):
        files = self.multi_files if self.multi_files else [self.file_path]
        
        def run():
            all_messages = []
            for f in files:
                self.add_log(f"📂 تحليل: {os.path.basename(f)}")
                msgs = parse_whatsapp_chat(f)
                self.add_log(f"✅ {len(msgs)} رسالة")
                all_messages.extend(msgs)
            
            total = len(all_messages)
            if total == 0:
                Clock.schedule_once(lambda dt: self.on_error("❌ لم يتم العثور على رسائل في الملف"))
                return
            
            Clock.schedule_once(lambda dt: self.update_count(0, total))
            self.add_log(f"📨 إجمالي: {total} رسالة")
            self.add_log("🚀 بدأ الإرسال...")
            
            def progress_cb(sent, total):
                Clock.schedule_once(lambda dt: self.update_count(sent, total))
            
            success, msg = send_to_telegram(
                self.token, self.chat_id, all_messages,
                progress_cb, self.batch_size
            )
            
            if success:
                Clock.schedule_once(lambda dt: self.on_success(msg))
            else:
                Clock.schedule_once(lambda dt: self.on_error(msg))
        
        thread = threading.Thread(target=run, daemon=True)
        thread.start()
    
    def update_count(self, sent, total):
        if total > 0:
            pct = int((sent / total) * 100)
            self.progress.value = pct
            self.count_label.text = f"{sent} / {total} رسالة ({pct}%)"
    
    def add_log(self, text):
        def _add(dt):
            self.log_label.text += text + "\n"
        Clock.schedule_once(_add)
    
    def on_success(self, msg):
        self.status_emoji.text = "✅"
        self.title_label.text = "تم بنجاح!"
        self.title_label.color = get_color_from_hex(COLOR_SUCCESS + "FF")
        self.progress.value = 100
        self.add_log(f"\n🎉 {msg}")
        self.done_btn.opacity = 1
        self.done_btn.disabled = False
    
    def on_error(self, msg):
        self.status_emoji.text = "❌"
        self.title_label.text = "حصل خطأ"
        self.title_label.color = get_color_from_hex(COLOR_ERROR + "FF")
        self.add_log(f"\n{msg}")
        self.done_btn.opacity = 1
        self.done_btn.disabled = False


class WA2TGApp(App):
    def build(self):
        self.title = "WA2TG - نقل واتساب لتيليجرام"
        
        sm = ScreenManager(transition=SlideTransition())
        sm.add_widget(HomeScreen(name='home'))
        sm.add_widget(SetupScreen(name='setup'))
        sm.add_widget(MultiScreen(name='multi'))
        sm.add_widget(ProgressScreen(name='progress'))
        
        return sm


if __name__ == '__main__':
    WA2TGApp().run()
