from PyQt6.QtWidgets import QSplashScreen, QLabel, QVBoxLayout, QWidget, QApplication
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap, QImage
import cv2
from pathlib import Path

class VideoSplashScreen(QSplashScreen):
    def __init__(self):
        super().__init__()
        # 获取主屏幕
        screen = QApplication.primaryScreen()
        screen_geometry = screen.geometry()
        self.screen_width = screen_geometry.width()
        self.screen_height = screen_geometry.height()
        
        # 设置窗口位置和大小为全屏
        self.width = self.screen_width
        self.height = self.screen_height
        self.setGeometry(0, 0, self.width, self.height)
        
        # 设置窗口属性
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | 
                          Qt.WindowType.FramelessWindowHint |
                          Qt.WindowType.Window)

        # 创建容器窗口小部件
        self.container = QWidget(self)
        layout = QVBoxLayout(self.container)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        # 创建视频标签
        self.video_label = QLabel()
        self.video_label.setFixedSize(self.width, self.height)
        layout.addWidget(self.video_label)

        # 固定容器大小
        self.container.setFixedSize(self.width, self.height)
        
        # 视频相关属性
        self.video_capture = None
        self.video_timer = QTimer()
        self.video_timer.timeout.connect(self.update_frame)
        self.total_frames = 0
        self.current_frame = 0
        self.should_loop = True  # 是否循环播放
        self._loading_progress = 0  # 内部进度变量

    def startVideo(self):
        video_path = str(Path(__file__).parent.parent / "startup.mp4")
        if Path(video_path).exists():
            self.video_capture = cv2.VideoCapture(video_path)
            if self.video_capture.isOpened():
                self.total_frames = int(self.video_capture.get(cv2.CAP_PROP_FRAME_COUNT))
                fps = self.video_capture.get(cv2.CAP_PROP_FPS)
                self.video_timer.start(int(1000/fps))
            else:
                print("无法打开视频文件")
                self.showImage()
        else:
            print(f"未找到视频文件: {video_path}")
            self.showImage()

    def update_frame(self):
        if self.video_capture is not None and self.video_capture.isOpened():
            ret, frame = self.video_capture.read()
            if ret:
                # 更新当前帧计数
                self.current_frame += 1
                
                # 调整帧大小以全屏显示，保持宽高比
                frame_height, frame_width = frame.shape[:2]
                aspect_ratio = frame_width / frame_height
                
                # 计算目标尺寸，确保视频充满屏幕
                target_width = self.width
                target_height = int(target_width / aspect_ratio)
                
                if target_height < self.height:
                    target_height = self.height
                    target_width = int(target_height * aspect_ratio)
                
                # 居中裁剪
                frame = cv2.resize(frame, (target_width, target_height))
                y_offset = (target_height - self.height) // 2
                x_offset = (target_width - self.width) // 2
                frame = frame[y_offset:y_offset + self.height,
                            x_offset:x_offset + self.width]
                
                # 转换并显示
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w, ch = frame.shape
                image = QImage(frame.data, w, h, ch * w, QImage.Format.Format_RGB888)
                self.video_label.setPixmap(QPixmap.fromImage(image))
            else:
                # 视频播放完毕，如果需要循环则重新开始
                if self.should_loop:
                    self.video_capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    self.current_frame = 0
                else:
                    self.video_timer.stop()
                    self.video_capture.release()
                    self.video_capture = None
                    self.showImage()

    def updateProgress(self, value):
        """保留进度更新功能，但不显示进度条"""
        self._loading_progress = value

    def getProgress(self):
        """获取当前进度"""
        return self._loading_progress

    def showImage(self):
        image_path = Path(__file__).parent.parent / "homepage.jpg"
        if image_path.exists():
            pixmap = QPixmap(str(image_path))
            scaled_pixmap = pixmap.scaled(self.width, self.height, 
                                        Qt.AspectRatioMode.KeepAspectRatio)
            self.setPixmap(scaled_pixmap)
        else:
            print(f"未找到图片文件: {image_path}")

    def stopVideo(self):
        """停止视频播放并清理资源"""
        self.should_loop = False
        if self.video_capture is not None:
            self.video_timer.stop()
            self.video_capture.release()
            self.video_capture = None

    def closeEvent(self, event):
        self.stopVideo()
        super().closeEvent(event)