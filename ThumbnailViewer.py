import sys, os, time, platform, shutil, ctypes, subprocess
import pvsubfunc, sdfileUtility
from send2trash import send2trash
from PIL import Image

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QStatusBar, QMainWindow, QLabel, QStackedWidget, QPushButton, QLineEdit, QSpinBox,
    QStyledItemDelegate, QAbstractItemView, QMessageBox, QComboBox
)
from PyQt5.QtGui import (
    QPixmap, QPainter, QColor, QIcon, QPalette, QMouseEvent, QWheelEvent,
    QMovie, QImageReader, QImage
)
from PyQt5.QtCore import (
    Qt, QRunnable, QThreadPool, QThread, pyqtSignal, QEvent, QSize, QRect,
    QTimer
)

#========================================
# 「初回のファイルコピー状態表示バッジ機能のON/OFF」
# 大量の画像を表示する場合、初回のファイル存在チェックに時間がかかり結構ストレスです
#  ・アプリ立ち上げ時にはコピー先フォルダが空前提の人はFalseに変更（もしくはHDDの人とか。。）
#  ・多少遅くても起動時にコピー先フォルダにファイルが存在するかチェックしたい人はTrueのままで
#========================================
DEF_CHECK_BADGE_IS_ON = True

#========================================
# 「プロンプト情報でのフィルタ機能」
# サムネイル作成と同時にPrompt情報を内部的に保持し、簡易なフィルター機能を実現します
#========================================
DEF_PROMPTFILTER_IS_ON = True

#========================================
# 「UIが固まらないようにサブスレッドであえてウェイト」
# これをFalseにするとサムネイル作成までの時間は6割くらいに減りますが、その間UI操作がほぼ不可能になります
# あまり大量の画像を表示しない人向け（せいぜい数百枚）
# それか上記のバッジ機能とフィルタ機能が不要な人は全てFalseにする分にはまだ実用可能かも
#========================================
DEF_ASYNC_WAIT_IS_ON = True

#========================================
# 「マウスでの画像表示をダブルクリックorシングルクリック切替」
# 従来のシングルクリックにしたい場合はFalseを指定してください
#========================================
DEF_MOUSE_DOUBLECLICK_IS_ON = True

#========================================
#= 「キー割り当ての変更」
#  Keyidは以下を参考に
#= https://doc.qt.io/qt-5/qt.html#Key-enum
#========================================
# アイコンリストと画像表示でキー定義
# カーソル移動 上
KEYS_CURSOR_UP = [Qt.Key_W, Qt.Key_Up]
# カーソル移動 下
KEYS_CURSOR_DOWN = [Qt.Key_S, Qt.Key_Down]
# カーソル移動 左
KEYS_CURSOR_LEFT = [Qt.Key_A, Qt.Key_Left]
# カーソル移動 右
KEYS_CURSOR_RIGHT = [Qt.Key_D, Qt.Key_Right]
# ページアップ
KEYS_PAGE_UP = [Qt.Key_2, Qt.Key_PageUp]
# ページダウン
KEYS_PAGE_DOWN = [Qt.Key_X, Qt.Key_PageDown]
# 全カーソルキー一覧（ここに登録しておかないとeventfilterとkeypressのイベントで2回の処理される）
KEYS_CURSOR_ALL = KEYS_CURSOR_UP + KEYS_CURSOR_DOWN + KEYS_CURSOR_LEFT + KEYS_CURSOR_RIGHT + KEYS_PAGE_UP + KEYS_PAGE_DOWN

# コピー1
KEYS_COPY1 = [Qt.Key_E, Qt.Key_Slash]
# コピー2
KEYS_COPY2 = [Qt.Key_Q, Qt.Key_Period]
# デリート
KEYS_DELETE = [Qt.Key_H, Qt.Key_Delete]
# 終了
KEYS_END = [Qt.Key_Escape, Qt.Key_Comma]
# 外部アプリにて画像を開く
KEYS_APP = [Qt.Key_R, Qt.Key_P]
# 保存済みのウインドウ・アイコンサイズへ切り替え
KEYS_OKINI_LOAD = [Qt.Key_8, Qt.Key_9, Qt.Key_0]
# 現在のウインドウ・アイコンサイズを保存
KEYS_OKINI_SAVE = [Qt.Key_F8, Qt.Key_F9, Qt.Key_F10]
# 設定保存時の確認用のテキスト（お気に入り画面サイズのキーを変更する場合にはここもあわせて）
KEYS_OKINI_NAME = ["Key_8", "Key_9", "Key_0"]
# 全機能キー一覧（ここに登録しておかないとeventfilterとkeypressのイベントで2回の処理される）
KEYS_FUNC_ALL = KEYS_COPY1 + KEYS_COPY2 + KEYS_DELETE + KEYS_END + KEYS_APP + KEYS_OKINI_LOAD + KEYS_OKINI_SAVE

# リスト時用の画像表示へ移動
KEYS_DISPIMG = [Qt.Key_F, Qt.Key_Enter, Qt.Key_Return]
# リスト時用の更新
KEYS_RECREATE = [Qt.Key_F5]

#----------------------------------------
# 定義（初期値など）
pvsubfunc._IS_DEBUG = 0 #デバッグログを出すなら1に
DEF_THUMBNAIL_SIZE = 256
DEF_THUMBNAIL_STEP = 64
DEF_FILENAME_TOP_LEN = 8
DEF_FILENAME_OMIT = ".."
DEF_FCOPY_DIR1 = "W:/_temp/ai"
DEF_FCOPY_DIR2 = "W:/_temp/ai2"
DEF_BADGE_ICON1 = "TV_badge1_128.png"
DEF_BADGE_ICON2 = "TV_badge2_128.png"
DEF_SOUND_BEEP = "PromptViewer_beep.wav"
DEF_SOUND_FCOPY_OK = "PromptViewer_filecopyok.wav"
DEF_SOUND_F_CANSEL = "PromptViewer_filecansel.wav"
DEF_SOUND_F_DELETE = "PromptViewer_filedelete.wav"
DEF_DIC_OKINI = {#iconsize,width,height,iconsize
    str(Qt.Key_8): [128, 1366, 892],     #128dotで10列5行
    str(Qt.Key_9): [256, 1860, 934],     #256dotで7列3行
    str(Qt.Key_0): [320, 1656, 1126]     #320dotで5列3行
}
DEF_FILTER_HISTORY_MAX = 20

#特定のアプリを起動する場合
#DEF_START_APP = "C:/Program Files/Honeyview/Honeyview.exe"
#DEF_START_PYFILE = ""
#DEF_START_WORKDIR = ""
#venvありのPythonファイルを起動する場合の指定方法
DEF_START_EXE_APP = "C:/tool/git/PromptViewer/venv/Scripts/pythonw.exe"
DEF_START_EXE_PYFILE = "C:/tool/git/PromptViewer/PromptViewer.py"
DEF_START_EXE_WORKDIR = "C:/tool/git/PromptViewer"

DEF_EVENT_IMAGEORLIST = 0
DEF_EVENT_COPYDIR1 = 1
DEF_EVENT_COPYDIR2 = 2
DEF_EVENT_DELETE = 3
DEF_EVENT_MOVELEFT = 10
DEF_EVENT_MOVERIGHT = 11
DEF_EVENT_PAGEUP = 12
DEF_EVENT_PAGEDOWN = 13
DEF_SUPPORT_IMAGE = (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".avif")
DEF_SUPPORT_MOVIE = (".gif", ".webp")
WINDOW_TITLE = "Thumbnail Viewer"
SETTINGS_FILE = "ThumbnailViewer_settings.json"
APP_WIDTH = 800
APP_HEIGHT = 480

#----------------------------------------
# 設定ファイルのキー名
GEOMETRY_X = "geometry-x"
GEOMETRY_Y = "geometry-y"
GEOMETRY_W = "geometry-w"
GEOMETRY_H = "geometry-h"
THUMBNAIL_SIZE = "thmbnail-size"
SOUND_BEEP = "sound-beep"
SOUND_FCOPY_OK = "sound-fcopy-ok"
SOUND_F_CANSEL = "sound-f-cansel"
SOUND_F_DELETE = "sound-f-delete"
IMAGE_FCOPY_DIR1 = "image-fcopy-dir1"
IMAGE_FCOPY_DIR2 = "image-fcopy-dir2"
START_EXE_APP_NAME = "start-exe-app-name"
START_EXE_PYTHON_NAME = "start-exe-python-name"
START_EXE_WORK_DIR = "start-exe-work-dir"
DIC_OKINI_SIZE = "dic-okini-size"
FILTER_HISTORY_STRINGS = "history-filter-strings"

#----------------------------------------
# サムネイルビューアクラス
class ThumbnailViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(WINDOW_TITLE)
        self.setGeometry(100, 100, APP_WIDTH, APP_HEIGHT)
        #ウインドウの最小サイズ（必須！指定しないと画像をいったん大きくすると小さく出来なくなる）
        self.setMinimumSize(640, 400)
        # 基本になるスタックウィジェット（アイコンリストの上に画像表示用のラベルをスタックする）
        self.stack = QStackedWidget()
        self.stack.setStyleSheet("color: white; font-size: 14px; background-color: #202224;")
        # アイコンリスト（下層スタック）
        self.list_widget = CustomListWidget()
        self.stack.addWidget(self.list_widget)
        self.setCentralWidget(self.stack)
        # 画像表示用ラベル（上層スタック）
        self.image_label = CustomLabel()
        self.stack.addWidget(self.image_label)
        # ステータスバー
        self.statusBar = QStatusBar()
        self.statusBar.setStyleSheet("color: white; font-size: 14px; background-color: #31363b;")
        self.setStatusBar(self.statusBar)

        # ステータスバー右側の選択中ファイル情報とアイコンサイズ設定部品
        self.filename = QLabel("")
        if DEF_PROMPTFILTER_IS_ON:
            self.pfilterbtnClr = QPushButton("clear")
            self.pfilterbtnSet = QPushButton("filter")
            self.pfiltercombo = QComboBox()
            self.pfiltercombo.setEditable(True)
            #self.pfiltercombo.setCompleter(None)
        self.buttonSmall = QPushButton(f"-{DEF_THUMBNAIL_STEP}")
        self.buttonLarge = QPushButton(f"+{DEF_THUMBNAIL_STEP}")
        self.thmsizeBox = QSpinBox()
        self.buttonSet = QPushButton("set")
        label = QLabel("Thumbnail size")
        self.statusBar.addPermanentWidget(self.filename)    #選択中ファイル情報
        if DEF_PROMPTFILTER_IS_ON:
            self.statusBar.addPermanentWidget(self.pfilterbtnClr)   #選択中ファイル情報
            self.statusBar.addPermanentWidget(self.pfilterbtnSet)   #選択中ファイル情報
            self.statusBar.addPermanentWidget(self.pfiltercombo)    #選択中ファイル情報

        self.statusBar.addPermanentWidget(self.buttonSmall) #アイコンサイズマイナスボタン
        self.statusBar.addPermanentWidget(self.thmsizeBox)  #アイコンサイズ入力欄
        self.statusBar.addPermanentWidget(self.buttonLarge) #アイコンサイズプラスボタン
        self.statusBar.addPermanentWidget(QLabel(" "))       #スペーサー代わりのラベル
        self.statusBar.addPermanentWidget(self.buttonSet)   #アイコンサイズ設定ボタン
        self.statusBar.addPermanentWidget(label)            #固定文字のラベル
        self.show_statusbar_mes(f"Drag and drop image files or folders")

        # 変数
        self.soundBeep = DEF_SOUND_BEEP
        self.soundFileCopyOK = DEF_SOUND_FCOPY_OK
        self.soundFileCansel = DEF_SOUND_F_CANSEL
        self.soundFileDelete = DEF_SOUND_F_DELETE
        self.imageFileCopyDir1 = DEF_FCOPY_DIR1
        self.imageFileCopyDir2 = DEF_FCOPY_DIR2
        self.startExeAppName = DEF_START_EXE_APP
        self.startExePythonName = DEF_START_EXE_PYFILE
        self.startExeWorkDir = DEF_START_EXE_WORKDIR
        self.thmbsize = DEF_THUMBNAIL_SIZE
        self.dic_okinisize = DEF_DIC_OKINI
        self.filterstrings = []

        # 設定ファイルがあれば読み込み
        if os.path.exists(SETTINGS_FILE):
            self.load_settings()

        # アイコンの設定
        try:
            #いちおう設定はしてるけどアイコンが化ける時は化ける
            #そもそもWindows側のicon管理の問題なような気がする（これに関係なくアイコンが化ける事があるし）
            #app.setWindowIcon(QIcon("res/ThumbnailViewer.ico"))
            self.setWindowIcon(QIcon("res/ThumbnailViewer.ico"))
        except Exception as e:
            print(e)

        # ウィジェットの設定
        self.setAcceptDrops(True)       #ドラッグドロップの許可
        # アイコンリスト
        self.list_widget.setContentsMargins(0, 0, 0, 0)
        self.list_widget.setViewMode(QListWidget.IconMode)
        self.list_widget.setIconSize(QPixmap(DEF_THUMBNAIL_SIZE, DEF_THUMBNAIL_SIZE).size())
        self.list_widget.setResizeMode(QListWidget.Adjust)
        self.list_widget.installEventFilter(self)
        self.list_widget.setDragEnabled(False)
        self.list_widget.setItemDelegate(BadgeDelegate())
        # スクロールバーでのスクロールを項目単位ではなく滑らかに
        self.list_widget.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)

        # スタック表示画像
        self.image_label.setAlignment(Qt.AlignCenter)

        if DEF_PROMPTFILTER_IS_ON:
            self.pfiltercombo.setFixedWidth(128)
            self.pfiltercombo.setFixedHeight(28)
            self.set_filterbutton_Style(self.pfilterbtnSet)
            self.set_filterbutton_Style(self.pfilterbtnClr)
            self.pfiltercombo.addItems(self.filterstrings)
            self.pfiltercombo.setEditText("")

        # ステータスバーのアイコンサイズ設定関連
        self.thmsizeBox.setMinimum(128)
        self.thmsizeBox.setMaximum(512)
        self.thmsizeBox.setValue(DEF_THUMBNAIL_SIZE)
        self.thmsizeBox.setFixedWidth(56)
        self.set_sizebutton_Style(self.buttonSmall)
        self.set_sizebutton_Style(self.buttonLarge)
        self.set_sizebutton_Style(self.buttonSet)

        # ウィジェットのイベント登録
        #self.list_widget.itemDoubleClicked.connect(self.on_item_double_clicked)
        self.list_widget.itemClicked.connect(self.on_item_clicked)
        self.list_widget.itemSelectionChanged.connect(self.change_selected_item)
        self.buttonSmall.clicked.connect(lambda: self.thmsizeBox.setValue(self.thmsizeBox.value() - DEF_THUMBNAIL_STEP))
        self.buttonLarge.clicked.connect(lambda: self.thmsizeBox.setValue(self.thmsizeBox.value() + DEF_THUMBNAIL_STEP))
        self.buttonSet.clicked.connect(self.recreate_thmbnail)
        self.image_label.labelMouseEvent.connect(self.on_label_mouse_event)
        self.image_label.setFocusPolicy(Qt.StrongFocus)

        if DEF_PROMPTFILTER_IS_ON:
            self.pfiltercombo.activated.connect(self.on_pfilter_activate)
            self.pfilterbtnSet.clicked.connect(self.on_pfilter_set)
            self.pfilterbtnClr.clicked.connect(self.on_pfilter_clr)

        # 初期値設定など
        self.set_thmbnail_size(self.thmbsize)
        self.subthread = None
        self.file_paths = []
        self.selected_file = ""
        self.thumbnailnum = 0
        self.pydir = os.path.dirname(os.path.abspath(__file__))
        self.isCreateThumbnail = False
        self.webpmovie = None   # 画像表示でwebpだった場合のプレイヤー
        self.lastcheckedpos = -1    # 最後の選択項目（選択が外れた場合の処理用）

    # サイズ変更ボタンのスタイル設定
    def set_sizebutton_Style(self, button):
        button.setStyleSheet(
            """
            QPushButton {
                background-color: #88BBEE;  /* 背景色 */
                color: #000000;  /* 文字色 */
            }
            QPushButton:disabled {
                background-color: #335577;
                color: #000000;
            }
            """
        )
        button.setFixedWidth(40)

    # フィルター機能ボタンのスタイル設定
    def set_filterbutton_Style(self, button):
        button.setStyleSheet(
            """
            QPushButton {
                background-color: #BBEE88;  /* 背景色 */
                color: #000000;  /* 文字色 */
            }
            QPushButton:disabled {
                background-color: #557733;
                color: #000000;
            }
            """
        )
        button.setFixedWidth(64)

    # フィルター機能のEnterもしくはリスト選択処理
    def on_pfilter_activate(self, index):
        self.doPfilterSet()

    # フィルター機能のセット処理
    def on_pfilter_set(self):
        self.doPfilterSet()

    def doPfilterSet(self):
        pos = self.get_selected_index()
        if pos == None: pos = 0
        fkey = self.pfiltercombo.currentText()

        counthit = 0

        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            prompt = item.data(Qt.UserRole + 2)
            isHit = fkey.lower() in prompt.lower()
            item.setHidden(not isHit)
            if isHit:
                counthit += 1

        newpos = pos
        if counthit > 0:
            # 一件以上ヒットした検索条件を保持する
            self.save_filter_keyword(fkey)

            #フィルタ後に前後に近い選択項目に移動する
            posbefore = -1
            posafter = -1
            for i in range(pos,-1,-1):
                item = self.list_widget.item(i)
                if not item.isHidden():
                    posbefore = i
                    break
            for i in range(pos, self.list_widget.count()):
                item = self.list_widget.item(i)
                if not item.isHidden():
                    posafter = i
                    break
            if posbefore == -1 and posafter == -1:
                newpos = 0
            elif posbefore == -1:
                newpos = posafter
            elif posafter == -1:
                newpos = posbefore
            else:
                if abs(pos - posbefore) < abs(pos - posafter):
                    newpos = posbefore
                else:
                    newpos = posafter
            pvsubfunc.dbgprint(f"now : {pos}, before : {posbefore}, after:{posafter}, newpos:{newpos}")
        else:
            newpos = 0
            pvsubfunc.dbgprint(f"not hit.")
        self.list_widget.setCurrentRow(newpos)
        QTimer.singleShot(0, self.scroll_later)
        if counthit == 0:
            self.show_selected_item_info(newpos,0)
        self.show_statusbar_mes(f"{counthit} files in {self.list_widget.count()} files matched the filter.")

    # フィルター機能のキーワード保存
    def save_filter_keyword(self, fkey):
        if not fkey: return     #空白は保存しない

        if fkey in self.filterstrings:
            self.filterstrings.remove(fkey)
        self.filterstrings.insert(0, fkey)
        self.filterstrings = self.filterstrings[:DEF_FILTER_HISTORY_MAX]    #履歴を個数制限
        self.pfiltercombo.clear()
        self.pfiltercombo.addItems(self.filterstrings)
        self.pfiltercombo.setCurrentText(fkey)
        #ウインドウ・アイコンサイズ保存と違って何度も実行すると思われるので、ここでは設定ファイルの保存はしない
        #self.save_settings()

    # フィルター機能のクリア処理
    def on_pfilter_clr(self):
        self.pfiltercombo.setEditText("")
        pos = self.get_selected_index()
        if pos == None: pos = 0
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            item.setHidden(False)
        self.list_widget.setCurrentRow(pos)
        QTimer.singleShot(0, self.scroll_later)
        self.show_statusbar_mes(f"filter cleared.")

    # サムネイルサイズの設定
    def set_thmbnail_size(self, tsize):
        self.thmbsize = tsize
        self.list_widget.setIconSize(QSize(tsize, tsize))
        self.thmsizeBox.setValue(tsize)

    # 終了時イベント
    def closeEvent(self, event):
        self.save_settings()
        super().closeEvent(event)

    # ドラッグエンターイベント
    def dragEnterEvent(self, event):
        #ToDo:サブスレッドが立ち上がるまでの物凄く短い期間でドロップすると落ちる事がある
        #安全策を取りたい場合は以下の判定を有効にしてサムネイル作成完了まではドロップ禁止にする
        #if self.get_status_createthumb(): return  #サムネイル作成中
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    # ドロップイベント
    def dropEvent(self, event):
        #ToDo:サブスレッドが立ち上がるまでの物凄く短い期間でドロップすると落ちる事がある
        #安全策を取りたい場合は以下の判定を有効にしてサムネイル作成完了まではドロップ禁止にする
        #if self.get_status_createthumb(): return  #サムネイル作成中

        #画像表示中にドロップされた場合にリストに戻る
        if self.stack.currentIndex() == 1:  # 画像表示中のみ有効
            self.backToList()

        self.lastcheckedpos = -1
        urls = event.mimeData().urls()
        file_paths = [url.toLocalFile() for url in urls]
        self.create_thumbnails(file_paths)

    # スタック表示画像からリストへの復帰処理
    def backToList(self, event=None):
        self.stop_WEbpMovie()
        self.stack.setCurrentIndex(0)

    # ウインドウリサイズイベント（スタック表示画像用。リストは自動でアジャスト）
    def resizeEvent(self, event):
        if self.stack.currentIndex() == 1 and self.selected_file != "":
            if self.selected_file.lower().endswith(DEF_SUPPORT_MOVIE):
                self.resize_MovieLabel(self.selected_file)
            else:
                self.resize_ImageLabel(self.selected_file)

    #ListWidght用のキーイベントフィルター
    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress:
            keyid = event.key()
            #Ctrlキー併用は別で処理する
            if event.modifiers() & Qt.ControlModifier:
                if keyid in {Qt.Key_W}:
                    self.close()
            #リストと画像表示の共通キー処理
            self.func_keyevent_common(keyid)
            #リスト表示時の画像表示処理
            if keyid in KEYS_DISPIMG:
                self.open_image_stack(self.get_selected_item_filename())
            #リスト表示時の更新処理
            if keyid in KEYS_RECREATE:
                if not self.get_status_createthumb():
                    file_paths = [self.get_selected_item_filename()]
                    self.create_thumbnails(file_paths)
            #キーの消費（eventFilter専用）
            if keyid in KEYS_CURSOR_ALL + KEYS_FUNC_ALL + KEYS_DISPIMG + KEYS_RECREATE:
                return True  # イベントをここで処理したとみなして消費
        return super().eventFilter(obj, event)

    #Lable用のキーイベント
    def keyPressEvent(self, event):
        keyid = event.key()
        #Ctrlキー併用は別で処理する
        if event.modifiers() & Qt.ControlModifier:
            if keyid in {Qt.Key_W}:
                self.close()
        #リストと画像表示の共通キー処理
        self.func_keyevent_common(keyid)
        if keyid in KEYS_CURSOR_ALL:
            #裏のアイコンリストでカーソル移動と共に画像を更新
            self.load_image_stack(self.get_selected_item_filename())
        #有効キー以外で画像表示を閉じてアイコンリストに戻る
        if keyid not in KEYS_CURSOR_ALL + KEYS_FUNC_ALL:
            if self.stack.currentIndex() == 1:  # 画像表示中のみ有効
                self.backToList()
        super().keyPressEvent(event)

    # キーイベント処理（アイコンリスト、画像ラベル共通）
    def func_keyevent_common(self, keyid):
        #カーソル移動
        if keyid in KEYS_CURSOR_ALL:
            if keyid in KEYS_CURSOR_UP:
                self.move_cursor(Qt.Key_Up)
            elif keyid in KEYS_CURSOR_DOWN:
                self.move_cursor(Qt.Key_Down)
            elif keyid in KEYS_CURSOR_LEFT:
                self.move_cursor(Qt.Key_Left)
            elif keyid in KEYS_CURSOR_RIGHT:
                self.move_cursor(Qt.Key_Right)
            elif keyid in KEYS_PAGE_UP:
                self.move_cursor(Qt.Key_PageUp)
            elif keyid in KEYS_PAGE_DOWN:
                self.move_cursor(Qt.Key_PageDown)
        #コピー処理1
        elif keyid in KEYS_COPY1:
            self.copy_file(self.get_selected_item_filename(), self.imageFileCopyDir1)
        #コピー処理2
        elif keyid in KEYS_COPY2:
            self.copy_file(self.get_selected_item_filename(), self.imageFileCopyDir2)
        #デリート処理
        elif keyid in KEYS_DELETE:
            self.delete_file(self.get_selected_item_filename(), self.get_selected_index())
        #アプリ起動
        elif keyid in KEYS_APP:
            self.start_app_file(self.get_selected_item_filename())
        #終了
        elif keyid in KEYS_END:
            self.close()
        #保存済みのウインドウ・アイコンサイズへ切り替え
        elif keyid in KEYS_OKINI_LOAD:
            self.load_okini_size(keyid)
        #現在のウインドウ・アイコンサイズを保存
        elif keyid in KEYS_OKINI_SAVE:
            self.save_okini_size(keyid)

    # 保存済みのウインドウ・アイコンサイズへ切り替え
    def load_okini_size(self, key):
        #連続してサムネイル生成処理が稼働すると問題が発生する可能性があるのでガードしておく
        #リスクが許容出来ればコメントアウトしてもよい
        if self.get_status_createthumb():
            self.show_statusbar_error(f"error : Thumbnail creation in progress.]")
            return

        sizelist = self.dic_okinisize[str(key)]
        if sizelist:
            self.thmsizeBox.setValue(sizelist[0])
            self.recreate_thmbnail()
            rect = self.geometry()
            self.setGeometry(rect.x(), rect.y(), sizelist[1], sizelist[2])

    # ウインドウ・アイコンサイズを保存
    def save_okini_size(self, key):
        keypos = KEYS_OKINI_SAVE.index(key)

        response = QMessageBox.question(self, "確認", f"現在のアイコン・ウインドウサイズを{KEYS_OKINI_NAME[keypos]}用に保存しますか？", QMessageBox.Yes | QMessageBox.No)
        if response != QMessageBox.Yes:
            return

        #サムネイルサイズの設定用スピンボックスの値ではなく、現在表示中のアイコンサイズを保存する
        self.dic_okinisize[str(KEYS_OKINI_LOAD[keypos])] = [self.thmbsize, self.geometry().width(), self.geometry().height()]
        self.show_statusbar_mes(f"saved icon and window size for {KEYS_OKINI_NAME[keypos]}.")
        self.save_settings()    #一応このタイミングで設定ファイルへも保存

    # カーソルキー判定処理
    # ページUp/Downは、3行表示している場合は2行分移動
    def move_cursor(self, direction):
        count = self.list_widget.count()
        nowpos = self.get_selected_index()
        hnum = self.get_list_hcount()
        vnum = max(1, self.get_list_vcount() - 1)   #表示行-1行分スクロール
        scrollnum = (hnum * vnum)   #横の項目数 * 行数で移動項目数
        #選択が外れた場合は前回選択中の位置から処理を継続
        #（選択項目が外れないようにしたため選択外れとキー操作がよほどクロスしない限りこの処理は働かない）
        pos = nowpos
        if pos == None:
            pos = self.lastcheckedpos

        if pos >= 0: #フォルダをドロップした時点で0を選択しているので-1はあり得ないが念のためチェック
            offset = 0
            if direction == Qt.Key_Up:
                offset = -hnum
            elif direction == Qt.Key_Down:
                offset = hnum
            elif direction == Qt.Key_Left:
                offset = -1
            elif direction == Qt.Key_Right:
                offset = 1
            elif direction == Qt.Key_PageUp:
                offset = -scrollnum
            elif direction == Qt.Key_PageDown:
                offset = scrollnum
            self.move_selected_item(offset)

    # カーソル移動処理（実際の移動先算出）
    # フィルター機能にあわせて、表示中の項目でのみ移動を行う
    def move_selected_item(self, offset):
        pos = self.get_selected_index()
        if pos == None: return

        serchofs = 1
        serchcount = 0
        lastcheckpos = -1
        pvsubfunc.dbgprint(f"pos : {pos}, offset : {offset}")
        if offset < 0: serchofs = -1
        newpos = pos + serchofs
        while newpos >= 0 and newpos < self.list_widget.count():
            item = self.list_widget.item(newpos)
            if not item.isHidden():     # 非表示でないアイテムを見つけた場合
                lastcheckpos = newpos
                serchcount += serchofs  # 表示中のアイテムをどれだけ移動したかカウント
                pvsubfunc.dbgprint(f"  serchcount : {serchcount}, lastcheckpos : {lastcheckpos}")
                if (serchcount == offset):
                    # 指定されたオフセット分表示中のアイテムを移動したので選択
                    self.list_widget.setCurrentRow(newpos)  # 新しい行を選択
                    return
            # 次のアイテムをチェック
            newpos += serchofs

        pvsubfunc.dbgprint(f"  giveup lastcheckpos : {lastcheckpos}")

        # 移動方向に有効なアイテムが無かった場合は移動しない（できない）
        if lastcheckpos >= 0:
            # 出来る限りオフセットに近い最後の表示中アイテムに移動
            lastcheckpos = max(0, min(lastcheckpos, self.list_widget.count() - 1))
            self.list_widget.setCurrentRow(lastcheckpos)

    # 現在選択しているリストのIndex（単体）を返す（未選択時はNone）
    def get_selected_index(self):
        pos = None
        index = self.list_widget.selectedIndexes()
        if index and len(index) > 0:
            pos = index[0].row()
        return pos

    # リストで選択中のファイル名を取得（フルパス）
    def get_selected_item_filename(self):
        filename = ""
        item = self.get_selected_item()
        if item:
            filename = item.data(Qt.UserRole)
        return filename

    # リストで選択中のアイテムを取得
    def get_selected_item(self):
        result_item = None
        item = self.list_widget.selectedItems()
        if item and len(item) > 0:
            result_item = item[0]
        return result_item

    # 画像のスタック表示
    def open_image_stack(self,file):
        if file != "":
            self.load_image_stack(file)
            self.stack.setCurrentIndex(1)

    # 画像のスタックラベルへの読み込み
    def load_image_stack(self,file):
        """毎度忘れる。。。
        sizemain = self.size()  #ウインドウのサイズ（これはステータスバーやメニューバーを含むのでダメ）
        sizecontent = self.centralWidget().size()   #コンテンツ領域のサイズ（これが正解）
        sizestack = self.stack.size()   #一番上のウィジェットのサイズ（ちなみにここは上と同じ）
        """
        if file != "":
            self.selected_file = file
            self.stop_WEbpMovie()
            if self.selected_file.lower().endswith(DEF_SUPPORT_MOVIE):
                self.webpmovie = QMovie(file)
                self.image_label.setMovie(self.webpmovie)
                self.webpmovie.setScaledSize(self.get_fit_size(QImageReader(file).size(), self.centralWidget().size()))
                self.webpmovie.start()
            else:
                self.resize_ImageLabel(self.selected_file)

    # 元のサイズをターゲットサイズにフィットさせた場合のサイズを取得
    def get_fit_size(self, size_org, size_target):
        scaled_width = size_target.width()
        scaled_height = int(size_org.height() * (scaled_width / size_org.width()))
        if scaled_height > size_target.height():
            scaled_height = size_target.height()
            scaled_width = int(size_org.width() * (scaled_height / size_org.height()))
        return QSize(scaled_width,scaled_height)

    # 動画のサイズの更新する（単純なスケールのみ）
    def resize_MovieLabel(self, file_path):
        self.webpmovie.setScaledSize(self.get_fit_size(QImageReader(file_path).size(), self.centralWidget().size()))

    # 画像のサイズを更新する
    def resize_ImageLabel(self, file_path):
        pixmap = get_QPixmap_from_imagefile(file_path)
        scaled_pixmap = pixmap.scaled(self.centralWidget().size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.image_label.setPixmap(scaled_pixmap)

    # webpを再生中なら停止する
    def stop_WEbpMovie(self):
        if self.webpmovie != None:
            self.webpmovie.stop()
            self.webpmovie = None

    # ファイルのコピー処理
    def copy_file(self, file_path, destdir):
        #コピー先ディレクトリを空にしていた場合は何もしない
        if not destdir: return

        isCopyOK = -1
        mes = ""
        if not os.path.exists(file_path):
            self.show_statusbar_error(f"error : not exist file [{file_path}]")
            return
        if not os.path.exists(destdir):
            self.show_statusbar_error(f"error : not exist dir [{destdir}]")
            return

        dest_file = f"{destdir}/{os.path.basename(file_path)}"
        if dest_file == file_path:
            self.show_statusbar_error(f"error : Same folder [{dest_file}]")
            return

        # コピー先に同名のファイルがすでに存在していれば削除のみ実行
        if os.path.exists(dest_file):
            try:
                os.remove(dest_file)
                isCopyOK = 0
                mes = f"copy cansel [{dest_file}]"
            except Exception as e:
                mes = f"error : copy cansel [{file_path}]"
        else:
            try:
                shutil.copy2(file_path, destdir)
                isCopyOK = 1
                mes = f"copyed [{dest_file}]"
            except Exception as e:
                mes = f"error : copy [{dest_file}]"

        # ファイルのコピー先ディレクトリにファイルが存在するかをバッジ表示
        item = self.get_selected_item()
        self.set_iconBadge(item, os.path.basename(file_path))

        # 音の再生のために処理が遅れるので音の再生はここでまとめて行う
        if isCopyOK == 1:
            self.show_statusbar_mes(mes)
            self.play_wave(self.soundFileCopyOK)
        elif isCopyOK == 0:
            self.show_statusbar_mes(mes)
            self.play_wave(self.soundFileCansel)
        else:
            self.show_statusbar_error(mes)

    # ファイルのデリート処理
    def delete_file(self, file, pos):
        isRemoveOK = False
        if pos < self.list_widget.count():
            self.list_widget.takeItem(pos)
            #管理テーブルからファイルを消す
            self.file_paths.remove(file)
        if os.path.exists(file):
            try:
                fullpath = os.path.abspath(file)
                #----memo----
                # os.removeだと即時削除、send2trashライブラリを使うとゴミ箱に入る
                # os.path.abspath(file)を使っているのは、
                # 通常のパス文字列    「C:/test/hoge.jpg」だとsend2trashで例外が発生するため、
                # OS依存のパス文字列  「C:\\test\\hoge.jpg」に変換する必要がある
                #------------
                #os.remove(file)     #きれいさっぱり消したい人用
                send2trash(os.path.abspath(file))    #念のためゴミ箱に捨てたい人用
                self.show_statusbar_mes(f"deleted [{file}]")
                isRemoveOK = True
            except Exception as e:
                self.show_statusbar_error(f"error : delete [{file}]")

        if self.list_widget.count() == 0:
            #表示する画像がないので空リストに戻るしかない
            self.backToList()
        else:
            if pos < self.list_widget.count() - 1:
                #まだ先のrowが存在するので元々の次の画像に移動
                self.list_widget.setCurrentRow(pos)
            else:
                #最終画像なので元々の前の画像に移動
                self.list_widget.setCurrentRow(self.list_widget.count() - 1)

        #画像表示中であれば新しい画像を表示
        if self.stack.currentIndex() == 1:  # 画像表示中のみ有効
            self.load_image_stack(self.get_selected_item_filename())

        #右下のステータスを更新
        self.change_selected_item()
        #サウンドの再生は処理後にしないと、画像の更新と音にずれがでる
        if isRemoveOK:
            self.play_wave(self.soundFileDelete)

    # 選択ファイルを外部アプリで開く
    def start_app_file(self, file):
        #未指定の場合はなにもしない
        if not self.startExeAppName: return

        workdir = self.startExeWorkDir
        if not os.path.isdir(workdir):
            self.show_statusbar_mes(f"warrning : start app workdir is not exit")
            workdir == ""

        try:
            #設定状況にあわせて外部アプリを起動
            if self.startExePythonName and workdir:
                subprocess.Popen([self.startExeAppName, self.startExePythonName, file], cwd=workdir)
            elif workdir:
                subprocess.Popen([self.startExeAppName, file], cwd=workdir)
            elif self.startExePythonName:
                subprocess.Popen([self.startExeAppName, self.startExePythonName, file])
            else:
                subprocess.Popen([self.startExeAppName, file])
        except Exception as e:
            self.show_statusbar_error(f"error : start app")

    # ステータス表示（通常）
    def show_statusbar_mes(self, mes):
        self.statusBar.showMessage(f"{mes}")

    # ステータス表示（エラー）
    def show_statusbar_error(self, mes):
        self.statusBar.showMessage(f"{mes}")
        self.play_wave(self.soundBeep)

    # 選択ファイルの状況表示
    def show_selected_item_info(self, pos, count):
        if count == 0:
            self.setWindowTitle(WINDOW_TITLE)
            return
        countlen = len(str(count))
        self.setWindowTitle(f"[{pos + 1:0{countlen}}/{count}] {self.get_selected_item_filename()}")
        #ここは結構見にくい位置なので、サムネイル作成状況とかどうでもいいものに変更
        #self.filename.setText(f"{self.get_selected_item_filename()} [{pos + 1:0{countlen}}/{count}] ")

    # サウンド再生
    def play_wave(self, file_name):
        #空指定の場合には何もしない
        if not file_name: return

        file_path = f"{self.pydir}/{file_name}"
        """
        if not os.path.exists(file_path): return
        sound = QSound(file_path)
        sound.play()
        while sound.isFinished() is False:
            app.processEvents()
        """
        #QSoundだとカーソル移動に違和感のあるケースがあるのでQMediaPlayerに変更
        pvsubfunc.play_wave(file_path)

    # アイコンリスト表示の横の数を取得
    def get_list_hcount(self):
        item_width = self.list_widget.sizeHintForColumn(0)
        widget_width  = self.list_widget.width()
        if item_width == 0:
            return 0
        horizontal_item_count = widget_width // item_width
        return max(1, horizontal_item_count)

    # アイコンリスト表示の縦の行数を取得
    def get_list_vcount(self):
        item_height = self.list_widget.sizeHintForRow(0)
        widget_height  = self.list_widget.height()
        if item_height == 0:
            return 0
        vertical_item_count = widget_height // item_height
        return max(1, vertical_item_count)

    # この方式だと右クリックのダブルクリックまで処理してしまってる
    # CustomListWidgetの中でmouseDoubleClickEventをオーバーライドして処理するように変更
    """
    # アイコンリストのダブルクリックイベント
    def on_item_double_clicked(self):
        #ダブルクリックかシングルクリックかの機能切替対応
        if DEF_MOUSE_DOUBLECLICK_IS_ON:
            self.open_image_stack(self.get_selected_item_filename())
    """

    # アイコンリストのクリックイベント
    def on_item_clicked(self, no):
        self.mouse_button_clicked(no)

    # スタック表示画像でのマウスイベント
    def on_label_mouse_event(self, no):
        self.mouse_button_clicked(no)

    # アイコンリスト、スタック表示画像でのマウスクリック処理
    def mouse_button_clicked(self, no):
        if no == DEF_EVENT_IMAGEORLIST:
            if self.stack.currentIndex() == 1:
                # 画像表示中は戻る
                self.backToList()
            else:
                # リストの場合は画像表示
                self.open_image_stack(self.get_selected_item_filename())
        elif no == DEF_EVENT_COPYDIR1:
            self.copy_file(self.get_selected_item_filename(), self.imageFileCopyDir1)
        elif no == DEF_EVENT_COPYDIR2:
            self.copy_file(self.get_selected_item_filename(), self.imageFileCopyDir2)
        elif no == DEF_EVENT_DELETE:    # 現在は未割当
            self.delete_file(self.get_selected_item_filename(), self.get_selected_index())
        elif no == DEF_EVENT_MOVELEFT:
            self.move_cursor(Qt.Key_Left)
            self.load_image_stack(self.get_selected_item_filename())
        elif no == DEF_EVENT_MOVERIGHT:
            self.move_cursor(Qt.Key_Right)
            self.load_image_stack(self.get_selected_item_filename())
        elif no == DEF_EVENT_PAGEUP:
            #ちょっと早すぎて使いにくいのでホイール操作は上下キーと同様に1行分だけに
            #self.move_cursor(Qt.Key_PageUp)
            self.move_cursor(Qt.Key_Up)
            self.load_image_stack(self.get_selected_item_filename())
        elif no == DEF_EVENT_PAGEDOWN:
            #ちょっと早すぎて使いにくいのでホイール操作は上下キーと同様に1行分だけに
            #self.move_cursor(Qt.Key_PageDown)
            self.move_cursor(Qt.Key_Down)
            self.load_image_stack(self.get_selected_item_filename())

    # アイコンリストの選択項目変更イベント
    def change_selected_item(self):
        pos = self.get_selected_index()
        #list_widgetはclearしてから実際に削除されるまでラグがある？のでfile_pathsでの判定に変更
        #count = self.list_widget.count()
        count = len(self.file_paths)
        if pos == None:
            pos = 0
            if self.lastcheckedpos >= 0:
                #選択が外れた場合は強引に前の選択項目をチェックされた事にする
                pos = self.lastcheckedpos
                self.list_widget.setCurrentRow(pos)
        else:
            self.lastcheckedpos = pos   #有効な選択のみ最後の選択番号として退避
        self.show_selected_item_info(pos, count)

    # アイコンサイズ変更時のサムネイル再作成処理
    def recreate_thmbnail(self):
        self.set_thmbnail_size(self.thmsizeBox.value())
        paths = self.file_paths[:]  #参照ではなくコピーしておく
        self.create_thumbnails(paths)

    # サムネイル作成状態の設定
    def set_status_createthumb(self, doing):
        self.isCreateThumbnail = doing
        if DEF_PROMPTFILTER_IS_ON:
            self.pfiltercombo.setEnabled(not doing)
            self.pfilterbtnSet.setEnabled(not doing)
            self.pfilterbtnClr.setEnabled(not doing)
        self.buttonSet.setEnabled(not doing)

    # サムネイル作成状態の取得
    def get_status_createthumb(self):
        return self.isCreateThumbnail

    # サムネイル生成処理
    def create_thumbnails(self, paths):
        if not paths or len(paths) == 0: return
        #リストをクリア
        if self.list_widget and self.list_widget.count() > 0:
            self.list_widget.scrollToItem(self.list_widget.item(0))
        self.file_paths.clear()
        self.thumbnailnum = 0
        self.list_widget.clear()
        self.set_status_createthumb(True)   #サムネイル作成開始
        #1ファイルだけがドロップされた場合には一つ上のフォルダがドロップされたことにする
        dropOneFile = ""
        if not os.path.isdir(paths[0]) and len(paths) == 1:
            dropOneFile = paths[0]
            paths[0] = os.path.dirname(paths[0])

        #ドロップされたファイル名リストを作成する（サムネイルは後）
        for path in paths:
            if os.path.isdir(path):
                # フォルダの場合
                for file_name in os.listdir(path):
                    #file_path = os.path.join(path, file_name)
                    file_path = f"{path}/{file_name}"
                    if self.is_image(file_path):
                        self.add_placeholder(file_path)
                        self.file_paths.append(file_path)
            elif self.is_image(path):
                # ファイルの場合
                self.add_placeholder(path)
                self.file_paths.append(path)
        #ドロップ数とサムネイル作成済み枚数の表示
        self.show_statusbar_mes(f"{len(self.file_paths)} file dropped.")
        self.show_thumbnail_info()
        #1ファイルだけがドロップされた場合、そのファイルまでスクロール＆選択状態にする
        if dropOneFile != "":
            """
            #メモ代わりに一か所だけ古い処理を残しておく
            for index in range(self.list_widget.count()):
                item = self.list_widget.item(index)
                if item.data(Qt.UserRole) == dropOneFile:
                    self.list_widget.setCurrentItem(item)
                    break
            """
            #高速なnextでのサーチに変更
            item = next((item for i in range(self.list_widget.count())
                    if (item := self.list_widget.item(i)).data(Qt.UserRole) == dropOneFile), None)
            if item:
                self.list_widget.setCurrentItem(item)
        else:
            itempos = self.lastcheckedpos
            #ファイルドロップによる新しいリスト表示
            if self.lastcheckedpos < 0:
                itempos = 0 #1ファイルだけのドロップではない場合は先頭を選択状態にする
            self.list_widget.setCurrentRow(itempos) #サムネイルの再作成の場合は同じ選択位置に

            #いったん描画をせずにscrollToItemをしても正しい位置にスクロールしない
            #->と思ったが、UIの強制更新でもだめ
            #QApplication.processEvents()
            #タイマーで処理を次のイベントループに変更してみる
            #->こちらは成功
            QTimer.singleShot(0, self.scroll_later)
            """
            item = self.list_widget.currentItem()
            self.list_widget.scrollToItem(item, QAbstractItemView.PositionAtCenter)
            """

        #横のマージンを減らしたい場合は有効にしても良い
        #縦のマージンは詰めるとアイコン下のラベルの2行表示が欠けてしまう
        """
        rect = self.list_widget.visualItemRect(self.list_widget.item(0))
        height = rect.height()
        defmargin = rect.width() - self.thmbsize
        margin = defmargin // 2
        self.list_widget.setGridSize(QSize(self.thmbsize + margin, height))
        """

        #サムネイル作成スレッドを起動
        self.start_subthread(self.file_paths, self.thmbsize)

    #次のイベントループでのスクロール処理用（サムネイル作成時のフォーカス移動用）
    def scroll_later(self):
        item = self.list_widget.currentItem()
        self.list_widget.scrollToItem(item, QAbstractItemView.PositionAtCenter)

    # ドロップファイル数とサムネイル生成状況の表示
    def show_thumbnail_info(self):
        filenum = len(self.file_paths)
        filelen = len(str(filenum))
        #self.show_statusbar_mes(f"[{self.thumbnailnum:0{filelen}}/{filenum}] file dropped.")
        self.filename.setText(f"Thumbnail created [{self.thumbnailnum:0{filelen}}/{filenum}] ")

    # サムネイル作成前の仮画像作成
    def add_placeholder(self, image_path):
        # プレースホルダーとして灰色画像を表示
        gray_pixmap = QPixmap(self.thmbsize, self.thmbsize)
        gray_pixmap.fill(Qt.gray)

        # アイテムの作成
        file_name = os.path.basename(image_path)
        short_name = self.truncate_filename(file_name)
        item = QListWidgetItem(f"{short_name}\nLoading...")
        item.setIcon(QIcon(gray_pixmap))
        item.setData(Qt.UserRole, image_path)           # ファイル名フルパス
        item.setData(Qt.UserRole + 1, (False, False))   # バッジ1、2のオンオフ
        item.setData(Qt.UserRole + 2, "")  # プロンプト情報
        self.list_widget.addItem(item)

    # サムネイル作成サブスレッド開始
    def start_subthread(self, file_paths, tsize):
        #サブスレッドが動いていれば停止を待つ
        self.stop_subthread()
        self.subthread = SubThread(file_paths, tsize)
        self.subthread.progress.connect(self.on_progress)  # 進捗通知を受け取る
        self.subthread.finished_signal.connect(self.on_finished)  # 終了通知を受け取る
        pvsubfunc.dbgprint(f"--start {self.subthread}")
        self.subthread.start()  # スレッドの開始

    # サムネイル作成サブスレッド停止
    def stop_subthread(self):
        if self.subthread is not None and self.subthread.isRunning():
            self.subthread.stop()
            self.subthread.wait()

    # サブスレッドからの進捗状況イベント
    def on_progress(self, progress, file_path, icon, original_size):
        item = next((item for i in range(self.list_widget.count())
                if (item := self.list_widget.item(i)).data(Qt.UserRole) == file_path), None)
        if item:
            # サムネイルと元画像サイズを更新
            file_name = os.path.basename(file_path)
            short_name = self.truncate_filename(file_name)
            if icon:
                item.setIcon(icon)
                item.setText(f"{short_name}\n{original_size}")
            else:
                item.setText(f"{short_name}\ndecode error.")

            #プロンプト情報取得もそれなりに時間はかかる
            if DEF_PROMPTFILTER_IS_ON:
                val = sdfileUtility.get_prompt_from_imgfile(file_path)
                if not val: val = ""
                item.setData(Qt.UserRole + 2, val)   # prompt情報

            #これをONにすると初回のサムネイル表示完了までに時間が余計にかかるようになる
            if DEF_CHECK_BADGE_IS_ON:
                #ファイルのコピー先ディレクトリにファイルが存在するかをバッジ表示
                self.set_iconBadge(item, file_name)

        #ドロップ数とサムネイル作成済み枚数の表示
        self.thumbnailnum = self.thumbnailnum + 1
        self.show_thumbnail_info()

    # サブスレッドの処理完了イベント
    def on_finished(self, strsubth):
        pvsubfunc.dbgprint(f"  ==end {strsubth}")
        self.subthread = None
        self.set_status_createthumb(False)   #サムネイル作成完了

    # コピー先ディレクトリに指定ファイルが存在するかをチェックしてバッジ情報を更新する
    def set_iconBadge(self, item, file):
        if item == None: return
        isExistDir1, isExistDir2 = self.file_exist_check(file)
        item.setData(Qt.UserRole + 1, (isExistDir2, isExistDir1))

    # Dir1、Dir2にファイルが存在するかチェックする
    def file_exist_check(self, file):
        #memo:ファイルチェックos.path.isfileだとかなり遅いので、os.path.existsに変える
        isDir1 = os.path.exists(f"{self.imageFileCopyDir1}/{file}")
        isDir2 = os.path.exists(f"{self.imageFileCopyDir2}/{file}")
        return isDir1, isDir2

    # 画像ファイルかチェック（拡張子のみ）
    def is_image(self, file_path):
        # 画像ファイルの拡張子チェック
        return file_path.lower().endswith(DEF_SUPPORT_IMAGE)

    # ファイル名の切りつめ処理（アイコンの幅までの省略表示用）
    def truncate_filename(self, file_name):
        #長いファイル名を先頭8文字と省略記号..、残りのn文字に切りつめる
        filemaxlen = self.thmbsize // 8 #サムネイルの幅で表示可能な文字数（だいたい）
        if len(file_name) <= filemaxlen:
            return file_name
        return f"{file_name[:DEF_FILENAME_TOP_LEN]}{DEF_FILENAME_OMIT}{file_name[(-filemaxlen + DEF_FILENAME_TOP_LEN + len(DEF_FILENAME_OMIT)):]}"

    # 設定ファイルのロード（項目がなかった場合は初期値）
    def load_settings(self):
        geox = pvsubfunc.read_value_from_config(SETTINGS_FILE, GEOMETRY_X)
        geoy = pvsubfunc.read_value_from_config(SETTINGS_FILE, GEOMETRY_Y)
        geow = pvsubfunc.read_value_from_config(SETTINGS_FILE, GEOMETRY_W)
        geoh = pvsubfunc.read_value_from_config(SETTINGS_FILE, GEOMETRY_H)
        if not any(val is None for val in [geox, geoy, geow, geoh]):
            self.setGeometry(geox, geoy, geow, geoh)
        val = pvsubfunc.read_value_from_config(SETTINGS_FILE, THUMBNAIL_SIZE)
        if val: self.thmbsize = val
        else: self.thmbsize = DEF_THUMBNAIL_SIZE

        #アイコン・ウインドウサイズを保持するディクショナリー型
        val = pvsubfunc.read_value_from_config(SETTINGS_FILE, DIC_OKINI_SIZE)
        if val: self.dic_okinisize = val
        else: self.dic_okinisize = DEF_DIC_OKINI

        self.filterstrings = pvsubfunc.read_list_from_config(SETTINGS_FILE, FILTER_HISTORY_STRINGS)
        if not self.filterstrings:
            self.filterstrings = []

        #要素が存在しない場合の初期値指定ありの関数に置き換え
        self.soundBeep = pvsubfunc.read_value_from_config(SETTINGS_FILE, SOUND_BEEP, DEF_SOUND_BEEP)
        self.soundFileCopyOK = pvsubfunc.read_value_from_config(SETTINGS_FILE, SOUND_FCOPY_OK, DEF_SOUND_FCOPY_OK)
        self.soundFileCansel = pvsubfunc.read_value_from_config(SETTINGS_FILE, SOUND_F_CANSEL, DEF_SOUND_F_CANSEL)
        self.soundFileDelete = pvsubfunc.read_value_from_config(SETTINGS_FILE, SOUND_F_DELETE, DEF_SOUND_F_DELETE)
        self.imageFileCopyDir1 = pvsubfunc.read_value_from_config(SETTINGS_FILE, IMAGE_FCOPY_DIR1, DEF_FCOPY_DIR1)
        self.imageFileCopyDir2 = pvsubfunc.read_value_from_config(SETTINGS_FILE, IMAGE_FCOPY_DIR2, DEF_FCOPY_DIR2)
        self.startExeAppName = pvsubfunc.read_value_from_config(SETTINGS_FILE, START_EXE_APP_NAME, DEF_START_EXE_APP)
        self.startExePythonName = pvsubfunc.read_value_from_config(SETTINGS_FILE, START_EXE_PYTHON_NAME, DEF_START_EXE_PYFILE)
        self.startExeWorkDir = pvsubfunc.read_value_from_config(SETTINGS_FILE, START_EXE_WORK_DIR, DEF_START_EXE_WORKDIR)

    # 設定ファイルのセーブ
    def save_settings(self):
        pvsubfunc.write_value_to_config(SETTINGS_FILE, GEOMETRY_X, self.geometry().x())
        pvsubfunc.write_value_to_config(SETTINGS_FILE, GEOMETRY_Y, self.geometry().y())
        pvsubfunc.write_value_to_config(SETTINGS_FILE, GEOMETRY_W, self.geometry().width())
        pvsubfunc.write_value_to_config(SETTINGS_FILE, GEOMETRY_H, self.geometry().height())
        pvsubfunc.write_value_to_config(SETTINGS_FILE, THUMBNAIL_SIZE, self.thmbsize)
        pvsubfunc.write_value_to_config(SETTINGS_FILE, SOUND_BEEP, self.soundBeep)
        pvsubfunc.write_value_to_config(SETTINGS_FILE, SOUND_FCOPY_OK, self.soundFileCopyOK)
        pvsubfunc.write_value_to_config(SETTINGS_FILE, SOUND_F_CANSEL, self.soundFileCansel)
        pvsubfunc.write_value_to_config(SETTINGS_FILE, SOUND_F_DELETE, self.soundFileDelete)
        pvsubfunc.write_value_to_config(SETTINGS_FILE, IMAGE_FCOPY_DIR1, self.imageFileCopyDir1)
        pvsubfunc.write_value_to_config(SETTINGS_FILE, IMAGE_FCOPY_DIR2, self.imageFileCopyDir2)
        pvsubfunc.write_value_to_config(SETTINGS_FILE, START_EXE_APP_NAME, self.startExeAppName)
        pvsubfunc.write_value_to_config(SETTINGS_FILE, START_EXE_PYTHON_NAME, self.startExePythonName)
        pvsubfunc.write_value_to_config(SETTINGS_FILE, START_EXE_WORK_DIR, self.startExeWorkDir)
        pvsubfunc.write_value_to_config(SETTINGS_FILE, DIC_OKINI_SIZE, self.dic_okinisize)
        pvsubfunc.write_list_from_config(SETTINGS_FILE, FILTER_HISTORY_STRINGS, self.filterstrings)

#----------------------------------------
# 画像のスタック表示用カスタムラベルクラス
class CustomLabel(QLabel):
    labelMouseEvent = pyqtSignal(int)

    def __init__(self):
        super().__init__()
    # マウスボタン押下イベント
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:     #左クリック
            self.mouse_notification(DEF_EVENT_IMAGEORLIST)
        elif event.button() == Qt.RightButton:  #右クリック
            self.mouse_notification(DEF_EVENT_COPYDIR1)
        elif event.button() == Qt.MiddleButton: #ミドルクリック
            self.mouse_notification(DEF_EVENT_COPYDIR2)
        """
        #サイドボタンでDelete処理などを実現する場合はここで
        elif event.button() == Qt.XButton1:     #サイドボタン1
            self.mouse_notification(DEF_EVENT_DELETE)
        elif event.button() == Qt.XButton2:     #サイドボタン2
            self.mouse_notification(DEF_EVENT_DELETE)
        """
    # マウスホイールイベント
    def wheelEvent(self, event: QWheelEvent):
        delta = event.angleDelta().y()
        if delta > 0:
            self.mouse_notification(DEF_EVENT_MOVELEFT)  #前の画像へ
        else:
            self.mouse_notification(DEF_EVENT_MOVERIGHT)  #次の画像へ
    # 上位へのイベント通知
    def mouse_notification(self, no):
        self.labelMouseEvent.emit(no)

#----------------------------------------
# アイコンリスト表示用のカスタムクラス
class CustomListWidget(QListWidget):
    itemClicked = pyqtSignal(int)

    def __init__(self):
        super().__init__()
    # マウスボタン押下イベント
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:     #左クリック
            #ダブルクリックかシングルクリックかの機能切替対応
            if not DEF_MOUSE_DOUBLECLICK_IS_ON:
                self.click_notification(event.pos(), DEF_EVENT_IMAGEORLIST)
        elif event.button() == Qt.RightButton:  #右クリック
            self.click_notification(event.pos(), DEF_EVENT_COPYDIR1)
        elif event.button() == Qt.MiddleButton: #ミドルクリック
            self.click_notification(event.pos(), DEF_EVENT_COPYDIR2)
        """
        #サイドボタンでDelete処理などを実現する場合はここを編集
        elif event.button() == Qt.XButton1:     #サイドボタン1
            self.click_notification(event.pos(), DEF_EVENT_DELETE)
        elif event.button() == Qt.XButton2:     #サイドボタン2
            self.click_notification(event.pos(), DEF_EVENT_DELETE)
        """
        super().mousePressEvent(event)
    # マウスダブルクリックイベント
    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            #ダブルクリックかシングルクリックかの機能切替対応
            if DEF_MOUSE_DOUBLECLICK_IS_ON:
                self.click_notification(event.pos(), DEF_EVENT_IMAGEORLIST)
        elif event.button() == Qt.RightButton:
            pass    #何もしない
        super().mouseDoubleClickEvent(event)
    # マウスホイールイベント
    def wheelEvent(self, event: QWheelEvent):
        delta = event.angleDelta().y()
        if delta > 0:
            self.itemClicked.emit(DEF_EVENT_PAGEUP)   #上にスクロール
        else:
            self.itemClicked.emit(DEF_EVENT_PAGEDOWN)   #下にスクロール
    # 上位へのイベント通知
    def click_notification(self, pos, no):
        item = self.itemAt(pos)
        if item:
            # どのキーでも処理前にリストの選択を実施
            self.setCurrentItem(item)
            self.itemClicked.emit(no)

#----------------------------------------
# サムネイル作成用のサブスレッドクラス
class SubThread(QThread):
    progress = pyqtSignal(int, str, QIcon, str)
    finished_signal = pyqtSignal(str)

    def __init__(self, file_paths, tsize):
        super().__init__()
        self.file_paths = file_paths
        self._is_running = False
        self.tsize = tsize
        self.ostype = -1
        system_name = platform.system()
        if system_name == "Windows":
            self.ostype = 0
        elif system_name in ["Linux", "Darwin"]:  # Darwin は macOS
            self.ostype = 1


    # メインループ
    # このループをマルチスレッドで処理しても結局アイコンの反映でUIが重くなってしまう
    # サブスレッドでアイコンデータを抱えて、何十個かまとめてからメインスレッドに通知しても結局アイコンデータのやり取りであまり早くならない
    def run(self):
        self._is_running = True
        pvsubfunc.dbgprint(f"     run {self}")
        for i, file_path in enumerate(self.file_paths):
            if not self._is_running:
                pvsubfunc.dbgprint(f"       stop ack {self}")
                break
            #最小のウェイト（入れると遅くなるけどUIは重くならない）
            if DEF_ASYNC_WAIT_IS_ON:
                self.sleep_microseconds(1)
            #ファイル削除後はもうファイルがない可能性がある
            if not os.path.exists(file_path):
                continue
            pixmap, width, height = self.create_thumbnail(file_path)
            original_size = ""
            if pixmap:
                original_size = self.get_imagesize_str(width,height)
            self.progress.emit(i + 1,file_path, QIcon(pixmap), original_size)

        self.finished_signal.emit(str(self))
        self._is_running = False
    # 停止処理
    def stop(self):
        self._is_running = False  # スレッド停止フラグをセット
        pvsubfunc.dbgprint(f"     stop req {self}")
    # サムネイル作成処理
    def create_thumbnail(self, file_path):
        pixmap = get_QPixmap_from_imagefile(file_path)
        width = pixmap.width()
        height = pixmap.height()
        if pixmap.isNull():
            return None
        # アスペクト比を維持してリサイズ
        thumb_size = self.tsize
        scaled_pixmap = pixmap.scaled(thumb_size, thumb_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        # 余白部分を黒塗りで埋める
        result_pixmap = QPixmap(thumb_size, thumb_size)
        result_pixmap.fill(Qt.black)
        painter = QPainter(result_pixmap)
        x_offset = (thumb_size - scaled_pixmap.width()) // 2
        y_offset = (thumb_size - scaled_pixmap.height()) // 2
        painter.drawPixmap(x_offset, y_offset, scaled_pixmap)
        painter.end()
        return result_pixmap, width, height
    # イメージサイズ文字列作成
    def get_imagesize_str(self, width, height):
        return f"{width} x {height}"

    # ミリ秒msec指定のスリープ関数
    def sleep_microseconds(self, milliseconds):
        system_name = platform.system()
        if self.ostype == 0:    #Windows
            ctypes.windll.kernel32.Sleep(milliseconds)
        elif self.ostype == 1: #Linux, macOS
            libc = ctypes.CDLL("libc.so.6" if system_name == "Linux" else "libSystem.dylib")
            libc.usleep(milliseconds * 1000)
        else:
            # 保険処理（これは1ms指定のはずなのに、普通に10ms以上かかったりするぼんくらタイマ）
            time.sleep(0.001)

#----------------------------------------
# バッジ表示用カスタムデリゲートクラス
class BadgeDelegate(QStyledItemDelegate):
    def __init__(self, parent = None):
        super().__init__(parent)
        # アイコンのバッジ
        self.icon_badge1 = None
        if os.path.exists(DEF_BADGE_ICON1):
            self.icon_badge1 = QPixmap(DEF_BADGE_ICON1)
        self.icon_badge2 = None
        if os.path.exists(DEF_BADGE_ICON2):
            self.icon_badge2 = QPixmap(DEF_BADGE_ICON2)

    def paint(self, painter, option, index):
        super().paint(painter, option, index)

        isBdg_Left, isBdg_right = index.data(Qt.UserRole + 1) or (False, False)

        icon_rect = option.rect
        icon_width = icon_rect.width()
        badge_size = icon_width // 4     #バッジサイズはアイコンの1/4
        badge_margin = 2
        badge_left = QRect(icon_rect.x() + badge_margin,
                            icon_rect.y() + badge_margin,
                            badge_size, badge_size)
        y_offset = icon_rect.y() + badge_margin

        painter.setRenderHint(QPainter.Antialiasing)

        if isBdg_right:
            x_offset = icon_rect.x() + icon_width - badge_size - badge_margin
            scaled_pixmap = self.icon_badge1.scaled(badge_size, badge_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            painter.drawPixmap(x_offset, y_offset, scaled_pixmap)
        if isBdg_Left:
            x_offset = icon_rect.x() + badge_margin
            scaled_pixmap = self.icon_badge2.scaled(badge_size, badge_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            painter.drawPixmap(x_offset, y_offset, scaled_pixmap)

# 画像ファイルからQPixmapを取得
def get_QPixmap_from_imagefile(file_path):
    if file_path.lower().endswith(".avif"):
        pixmap = get_QPixmap_from_avif(file_path)
    else:
        pixmap = QPixmap(file_path)
    return pixmap

# avifファイルからQPixmapを取得
def get_QPixmap_from_avif(file_path):
    img = Image.open(file_path)
    img = img.convert("RGBA")  # Ensure the image is in RGBA format
    data = img.tobytes("raw", "RGBA")
    qimage = QImage(data, img.width, img.height, QImage.Format_RGBA8888)
    pixmap = QPixmap.fromImage(qimage)
    return pixmap

#----------------------------------------
# メイン
if __name__ == "__main__":
    app = QApplication(sys.argv)
    #ここでアイコン設定しても変わらず。。
    #app.setWindowIcon(QIcon("res/ThumbnailViewer.ico"))
    viewer = ThumbnailViewer()
    viewer.show()
    sys.exit(app.exec_())
