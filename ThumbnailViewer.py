import sys
import os
import shutil
import time
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QStatusBar, QMainWindow, QLabel, QStackedWidget, QPushButton, QLineEdit, QSpinBox
)
from PyQt5.QtGui import (
    QPixmap, QPainter, QColor, QIcon, QPalette, QMouseEvent, QWheelEvent
)
from PyQt5.QtCore import (
    Qt, QRunnable, QThreadPool, QThread, pyqtSignal, QEvent, QSize
)
from PyQt5.QtMultimedia import QSound
import pvsubfunc

pvsubfunc._IS_DEBUG = 0 #デバッグログを出すなら1に
DEF_THUMBNAIL_SIZE = 256
DEF_THUMBNAIL_STEP = 16
DEF_FILENAME_TOP_LEN = 8
DEF_FILENAME_OMIT = ".."
DEF_FCOPY_DIR1 = "W:/_temp/ai"
DEF_FCOPY_DIR2 = "W:/_temp/ai2"

WINDOW_TITLE = "Thumbnail Viewer"
SETTINGS_FILE = "ThumbnailViewer_settings.json"
GEOMETRY_X = "geometry-x"
GEOMETRY_Y = "geometry-y"
GEOMETRY_W = "geometry-w"
GEOMETRY_H = "geometry-h"
THUMBNAIL_SIZE = "thmbnail-size"
SOUND_BEEP = "sound-beep"
SOUND_FCOPY_OK = "sound-fcopy-ok"
SOUND_F_CANSEL = "sound-f-cansel"
IMAGE_FCOPY_DIR1 = "image-fcopy-dir1"
IMAGE_FCOPY_DIR2 = "image-fcopy-dir2"
APP_WIDTH = 800
APP_HEIGHT = 480

#========================================
#= キー割り当ての変更時のKeyidは以下を参考に
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
# 全カーソルキー一覧
KEYS_CURSOR_ALL = KEYS_CURSOR_UP + KEYS_CURSOR_DOWN + KEYS_CURSOR_LEFT + KEYS_CURSOR_RIGHT
# コピー1
KEYS_COPY1 = [Qt.Key_E, Qt.Key_Slash]
# コピー2
KEYS_COPY2 = [Qt.Key_Q, Qt.Key_Period]
# 画像表示へ移動
KEYS_DISPIMG = [Qt.Key_F, Qt.Key_Enter, Qt.Key_Return]
# 終了
KEYS_END = [Qt.Key_Escape, Qt.Key_Comma]

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
        self.buttonSmall = QPushButton(f"-{DEF_THUMBNAIL_STEP}")
        self.buttonLarge = QPushButton(f"+{DEF_THUMBNAIL_STEP}")
        self.thmsizeBox = QSpinBox()
        self.buttonSet = QPushButton("set")
        label = QLabel("Thumbnail size")
        spacer = QLabel()
        self.statusBar.addPermanentWidget(self.filename)    #選択中ファイル情報
        self.statusBar.addPermanentWidget(self.buttonSmall) #アイコンサイズマイナスボタン
        self.statusBar.addPermanentWidget(self.thmsizeBox)  #アイコンサイズ入力欄
        self.statusBar.addPermanentWidget(self.buttonLarge) #アイコンサイズプラスボタン
        self.statusBar.addPermanentWidget(spacer)           #スペーサー代わりのラベル
        self.statusBar.addPermanentWidget(self.buttonSet)   #アイコンサイズ設定ボタン
        self.statusBar.addPermanentWidget(label)            #固定文字のラベル
        self.show_statusbar_mes(f"Drag and drop image files or folders")

        # 変数
        self.soundBeep = "PromptViewer_beep.wav"
        self.soundFileCopyOK = "PromptViewer_filecopyok.wav"
        self.soundFileCansel = "PromptViewer_filecansel.wav"
        self.imageFileCopyDir1 = DEF_FCOPY_DIR1
        self.imageFileCopyDir2 = DEF_FCOPY_DIR2
        self.thmbsize = DEF_THUMBNAIL_SIZE

        # 設定ファイルがあれば読み込み
        if os.path.exists(SETTINGS_FILE):
            self.load_settings()

        # ウィジェットの設定
        self.setAcceptDrops(True)       #ドラッグドロップの許可
        # アイコンリスト
        self.list_widget.setContentsMargins(0, 0, 0, 0)
        self.list_widget.setViewMode(QListWidget.IconMode)
        self.list_widget.setIconSize(QPixmap(DEF_THUMBNAIL_SIZE, DEF_THUMBNAIL_SIZE).size())
        self.list_widget.setResizeMode(QListWidget.Adjust)
        self.list_widget.installEventFilter(self)
        self.list_widget.setDragEnabled(False)
        # スタック表示画像
        self.image_label.setAlignment(Qt.AlignCenter)
        # ステータスバーのアイコンサイズ設定関連
        self.buttonSmall.setFixedWidth(40)
        self.buttonLarge.setFixedWidth(40)
        self.thmsizeBox.setMinimum(128)
        self.thmsizeBox.setMaximum(512)
        self.thmsizeBox.setValue(DEF_THUMBNAIL_SIZE)
        self.thmsizeBox.setFixedWidth(56)
        self.buttonSet.setFixedWidth(64)
        spacer.setFixedWidth(16)
        # ウィジェットのイベント登録
        self.list_widget.itemDoubleClicked.connect(self.on_item_double_clicked)
        self.list_widget.itemClicked.connect(self.on_item_clicked)
        self.list_widget.itemSelectionChanged.connect(self.change_selected_item)
        self.buttonSmall.clicked.connect(lambda: self.thmsizeBox.setValue(self.thmsizeBox.value() - DEF_THUMBNAIL_STEP))
        self.buttonLarge.clicked.connect(lambda: self.thmsizeBox.setValue(self.thmsizeBox.value() + DEF_THUMBNAIL_STEP))
        self.buttonSet.clicked.connect(self.recreate_thmbnail)
        self.image_label.labelMouseEvent.connect(self.on_label_mouse_event)
        self.image_label.setFocusPolicy(Qt.StrongFocus)

        # 初期値設定など
        self.set_thmbnail_size(self.thmbsize)
        self.subthread = None
        self.file_paths = []
        self.selected_file = ""
        self.thumbnailnum = 0
        self.pydir = os.path.dirname(os.path.abspath(__file__))
        self.isCreateThumbnail = False

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
        if self.get_status_createthumb():
            return  #サムネイル作成中
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    # ドロップイベント
    def dropEvent(self, event):
        if self.get_status_createthumb():
            return  #サムネイル作成中
        urls = event.mimeData().urls()
        file_paths = [url.toLocalFile() for url in urls]
        self.create_thumbnails(file_paths)

    # スタック表示画像からリストへの復帰処理
    def backToList(self, event=None):
        self.stack.setCurrentIndex(0)

    # ウインドウリサイズイベント（スタック表示画像用。リストは自動でアジャスト）
    def resizeEvent(self, event):
        if self.stack.currentIndex() == 1 and self.selected_file != "":
            pixmap = QPixmap(self.selected_file)
            scaled_pixmap = pixmap.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.image_label.setPixmap(scaled_pixmap)

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
            #キーの消費（eventFilter専用）
            if keyid in KEYS_CURSOR_ALL + KEYS_COPY1 + KEYS_COPY2 + KEYS_END + KEYS_DISPIMG:
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
        if keyid not in KEYS_CURSOR_ALL + KEYS_COPY1 + KEYS_COPY2 + KEYS_END:
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
        #コピー処理1
        if keyid in KEYS_COPY1:
            self.copy_file(self.get_selected_item_filename(), self.imageFileCopyDir1)
        #コピー処理2
        if keyid in KEYS_COPY2:
            self.copy_file(self.get_selected_item_filename(), self.imageFileCopyDir2)
        #終了
        if keyid in KEYS_END:
            self.close()

    # カーソル移動処理
    def move_cursor(self, direction):
        index = self.list_widget.selectedIndexes()
        count = self.list_widget.count()
        if index and len(index) > 0:
            pos = index[0].row()
            row = self.get_list_hcount()
            if direction == Qt.Key_Up:
                self.list_widget.setCurrentRow(max(0, pos - row))
            elif direction == Qt.Key_Down:
                self.list_widget.setCurrentRow(min(count - 1, pos + row))
            elif direction == Qt.Key_Left:
                self.list_widget.setCurrentRow(max(0, pos - 1))
            elif direction == Qt.Key_Right:
                self.list_widget.setCurrentRow(min(count - 1, pos + 1))

    # リストで選択中のファイル名を取得（フルパス）
    def get_selected_item_filename(self):
        filename = ""
        item = self.list_widget.selectedItems()
        if item and len(item) > 0:
            filename = item[0].data(Qt.UserRole)
        return filename

    # 画像のスタック表示
    def open_image_stack(self,file):
        if file != "":
            self.load_image_stack(file)
            self.stack.setCurrentIndex(1)

    # 画像のスタックラベルへの読み込み
    def load_image_stack(self,file):
        if file != "":
            self.selected_file = file
            pixmap = QPixmap(self.selected_file)
            scaled_pixmap = pixmap.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.image_label.setPixmap(scaled_pixmap)

    # ファイルのコピー処理
    def copy_file(self, file, destdir):
        if not os.path.isfile(file):
            self.show_statusbar_error(f"not exist file [{file}]")
            return
        if not os.path.isdir(destdir):
            self.show_statusbar_error(f"not exist dir [{destdir}]")
            return

        dest_file = f"{destdir}/{os.path.basename(file)}"

        # コピー先に同名のファイルがすでに存在していれば削除のみ実行
        if os.path.exists(dest_file):
            os.remove(dest_file)
            self.show_statusbar_mes(f"copy cansel [{dest_file}]")
            self.play_wave(self.soundFileCansel)
            return

        shutil.copy2(file, destdir)
        self.show_statusbar_mes(f"copyed [{dest_file}]")
        self.play_wave(self.soundFileCopyOK)

    # ステータス表示（通常）
    def show_statusbar_mes(self, mes):
        self.statusBar.showMessage(f"{mes}")

    # ステータス表示（エラー）
    def show_statusbar_error(self, mes):
        self.statusBar.showMessage(f"{mes}")
        self.play_wave(self.soundBeep)

    # サウンド再生
    def play_wave(self, file_name):
        file_path = f"{self.pydir}/{file_name}"
        if not os.path.isfile(file_path): return
        sound = QSound(file_path)
        sound.play()
        while sound.isFinished() is False:
            app.processEvents()

    # アイコンリスト表示の横の数を取得
    def get_list_hcount(self):
        item_width = self.list_widget.sizeHintForColumn(0)
        widget_width  = self.list_widget.width()
        if item_width == 0:
            return 0
        horizontal_item_count = widget_width // item_width
        return max(1, horizontal_item_count)

    # アイコンリストのダブルクリックイベント
    def on_item_double_clicked(self):
        self.open_image_stack(self.get_selected_item_filename())

    # アイコンリストのクリックイベント
    def on_item_clicked(self, no):
        self.mouse_button_clicked(no)

    # スタック表示画像でのマウスイベント
    def on_label_mouse_event(self, no):
        self.mouse_button_clicked(no)

    # アイコンリスト、スタック表示画像でのマウスクリック処理
    def mouse_button_clicked(self, no):
        if no == 0:     #左クリック
            if self.stack.currentIndex() == 1:  # 画像表示中のみ有効
                self.backToList()
        elif no == 1:
            self.copy_file(self.get_selected_item_filename(), self.imageFileCopyDir1)
        elif no == 2:
            self.copy_file(self.get_selected_item_filename(), self.imageFileCopyDir2)
        elif no == 3:
            self.move_cursor(Qt.Key_Left)
            self.load_image_stack(self.get_selected_item_filename())
        elif no == 4:
            self.move_cursor(Qt.Key_Right)
            self.load_image_stack(self.get_selected_item_filename())

    # アイコンリストの選択項目変更イベント
    def change_selected_item(self):
        pos = 0
        index = self.list_widget.selectedIndexes()
        if index and len(index) > 0:
            pos = index[0].row()
        count = self.list_widget.count()
        countlen = len(str(count))
        self.filename.setText(f"{self.get_selected_item_filename()} [{pos:0{countlen}}/{count}] ")

    # アイコンサイズ変更時のサムネイル再作成処理
    def recreate_thmbnail(self):
        self.set_thmbnail_size(self.thmsizeBox.value())
        paths = self.file_paths[:]  #参照ではなくコピーしておく
        self.create_thumbnails(paths)

    # サムネイル作成状態の設定
    def set_status_createthumb(self, doing):
        self.isCreateThumbnail = doing
        self.buttonSet.setEnabled(not doing)

    # サムネイル作成状態の取得
    def get_status_createthumb(self):
        #ToDo:サブスレッドが立ち上がるまでの物凄く短い期間でドロップすると落ちる事がある
        #その場合は以下の処理を入れ替えて、サムネイル作成完了まではドロップ禁止にする
        return False
        #return self.isCreateThumbnail

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
                # フォルダ内の画像を取得
                for file_name in os.listdir(path):
                    #file_path = os.path.join(path, file_name)
                    file_path = f"{path}/{file_name}"
                    if self.is_image(file_path):
                        self.add_placeholder(file_path)
                        self.file_paths.append(file_path)
            elif self.is_image(path):
                # 単一画像の場合
                self.add_placeholder(path)
                self.file_paths.append(path)
        #ドロップ数とサムネイル作成済み枚数の表示
        self.show_thumbnail_info()
        #ファイルだけがドロップされた場合、そのファイルまでスクロール＆選択状態にする
        if dropOneFile != "":
            for index in range(self.list_widget.count()):
                item = self.list_widget.item(index)
                if item.data(Qt.UserRole) == dropOneFile:
                    self.list_widget.setCurrentItem(item)
                    break

        rect = self.list_widget.visualItemRect(self.list_widget.item(0))
        #横のマージンを減らしたい場合は有効にしても良い
        #縦のマージンは詰めるとアイコン下のラベルの2行表示が欠けてしまう
        """
        height = rect.height()
        defmargin = rect.width() - self.thmbsize
        margin = defmargin // 2
        self.list_widget.setGridSize(QSize(self.thmbsize + margin, height))
        """

        #サムネイル作成スレッドを起動
        self.start_subthread(self.file_paths, self.thmbsize)

    # ドロップファイル数とサムネイル生成状況の表示
    def show_thumbnail_info(self):
        filenum = len(self.file_paths)
        filelen = len(str(filenum))
        self.show_statusbar_mes(f"[{self.thumbnailnum:0{filelen}}/{filenum}] file dropped.")

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
        item.setData(Qt.UserRole, image_path)
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
    def on_progress(self, progress, file_path, pixmap, original_size):
        for index in range(self.list_widget.count()):
            item = self.list_widget.item(index)
            if item.data(Qt.UserRole) == file_path:
                # サムネイルと元画像サイズを更新
                file_name = os.path.basename(file_path)
                short_name = self.truncate_filename(file_name)
                if pixmap:
                    item.setIcon(QIcon(pixmap))
                    item.setText(f"{short_name}\n{original_size}")
                else:
                    item.setText(f"{short_name}\ndecode error.")
                #ドロップ数とサムネイル作成済み枚数の表示
                self.thumbnailnum = self.thumbnailnum + 1
                self.show_thumbnail_info()
                break

    # サブスレッドの処理完了イベント
    def on_finished(self, strsubth):
        pvsubfunc.dbgprint(f"  ==end {strsubth}")
        self.subthread = None
        self.set_status_createthumb(False)   #サムネイル作成完了

    # 画像ファイルかチェック（拡張子のみ）
    def is_image(self, file_path):
        # 画像ファイルの拡張子チェック
        return file_path.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"))

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

        self.soundBeep = pvsubfunc.read_value_from_config(SETTINGS_FILE, SOUND_BEEP)
        if not self.soundBeep or self.soundBeep == "":
            self.soundBeep = "PromptViewer_beep.wav"
        self.soundFileCopyOK = pvsubfunc.read_value_from_config(SETTINGS_FILE, SOUND_FCOPY_OK)
        if not self.soundFileCopyOK or self.soundFileCopyOK == "":
            self.soundFileCopyOK = "PromptViewer_filecopyok.wav"
        self.soundFileCansel = pvsubfunc.read_value_from_config(SETTINGS_FILE, SOUND_F_CANSEL)
        if not self.soundFileCansel or self.soundFileCansel == "":
            self.soundFileCansel = "PromptViewer_filecansel.wav"
        self.imageFileCopyDir1 = pvsubfunc.read_value_from_config(SETTINGS_FILE, IMAGE_FCOPY_DIR1)
        if not self.imageFileCopyDir1 or self.imageFileCopyDir1 == "":
            self.imageFileCopyDir1 = DEF_FCOPY_DIR1
        self.imageFileCopyDir2 = pvsubfunc.read_value_from_config(SETTINGS_FILE, IMAGE_FCOPY_DIR2)
        if not self.imageFileCopyDir2 or self.imageFileCopyDir2 == "":
            self.imageFileCopyDir2 = DEF_FCOPY_DIR2

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
        pvsubfunc.write_value_to_config(SETTINGS_FILE, IMAGE_FCOPY_DIR1, self.imageFileCopyDir1)
        pvsubfunc.write_value_to_config(SETTINGS_FILE, IMAGE_FCOPY_DIR2, self.imageFileCopyDir2)

#----------------------------------------
# 画像のスタック表示用カスタムラベルクラス
class CustomLabel(QLabel):
    labelMouseEvent = pyqtSignal(int)

    def __init__(self):
        super().__init__()
    # マウスボタン押下イベント
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.mouse_notification(0)  #左クリック
        elif event.button() == Qt.RightButton:
            self.mouse_notification(1)  #右クリック
        elif event.button() == Qt.MiddleButton:
            self.mouse_notification(2)  #ミドルクリック
    # マウスホイールイベント
    def wheelEvent(self, event: QWheelEvent):
        delta = event.angleDelta().y()
        if delta > 0:
            self.mouse_notification(3)  #上スクロール
        else:
            self.mouse_notification(4)  #下スクロール
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
        if event.button() == Qt.LeftButton:
            self.click_notification(event.pos(), 0)  #左クリック
        elif event.button() == Qt.RightButton:
            self.click_notification(event.pos(), 1)  #右クリック
        elif event.button() == Qt.MiddleButton:
            self.click_notification(event.pos(), 2)  #ミドルクリック
        super().mousePressEvent(event)
    # 上位へのイベント通知
    def click_notification(self, pos, no):
        item = self.itemAt(pos)
        if item:
            # どのキーでも処理前にリストの選択を実施
            self.setCurrentItem(item)
            self.itemClicked.emit(no)

#----------------------------------------
# サムネイル作成用のサブスレッド
class SubThread(QThread):
    progress = pyqtSignal(int, str, QPixmap, str)
    finished_signal = pyqtSignal(str)

    def __init__(self, file_paths, tsize):
        super().__init__()
        self.file_paths = file_paths
        self._is_running = False
        self.tsize = tsize
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
            #time.sleep(0.001) #最小のウェイト（入れると遅くなるけどUIは重くならない）
            pixmap, width, height = self.create_thumbnail(file_path)
            original_size = ""
            if pixmap:
                original_size = self.get_imagesize_str(width,height)
            self.progress.emit(i + 1,file_path, pixmap, original_size)

        self.finished_signal.emit(str(self))
        self._is_running = False
    # 停止処理
    def stop(self):
        self._is_running = False  # スレッド停止フラグをセット
        pvsubfunc.dbgprint(f"     stop req {self}")
    # サムネイル作成処理
    def create_thumbnail(self, file_path):
        pixmap = QPixmap(file_path)
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

#----------------------------------------
# メイン
if __name__ == "__main__":
    app = QApplication(sys.argv)
    viewer = ThumbnailViewer()
    viewer.show()
    sys.exit(app.exec_())
