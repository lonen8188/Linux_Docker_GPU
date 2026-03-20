import cv2
import torch
import base64
import time
import os
from ultralytics import YOLO

class AiStreamService:
    _model = None
    _target_label = ""  # 실시간 감시 타겟 (사용자 입력값)
    _device = 'cuda' if torch.cuda.is_available() else 'cpu'

    @classmethod
    def load_model(cls):
        """GPU 가속 기반 YOLOv8 모델 로드"""
        if cls._model is None:
            # 성공하셨던 yolov8n.pt 모델 및 CUDA 설정
            cls._model = YOLO('yolov8n.pt')
            cls._model.to(cls._device)
            print(f"AI Model Loaded on: {cls._device}")
        return cls._model

    @classmethod
    def set_target(cls, label):
        """프론트엔드에서 받은 감시 타겟 설정"""
        cls._target_label = label.strip().lower()

    @classmethod
    def run_rtsp_stream(cls, socketio, rtsp_url):
        # 1. H.265 대응 및 TCP 강제 설정
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|stimeout;5000000"
        
        cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1) 
        
        if not cap.isOpened():
            print(f"[ERROR] RTSP 연결 실패: {rtsp_url}")
            return

        model = cls.load_model()
        frame_count = 0
        print(f"[START] AI 모니터링 시작 (Device: {cls._device})")

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                socketio.sleep(0.1)
                continue

            frame = cv2.resize(frame, (640, 480))

            frame_count += 1
            # 성능 최적화: 3프레임당 1회만 분석
            if frame_count % 3 != 0:
                continue

            # 2. GPU 기반 추론 (imgsz=640으로 성능 확보)
            results = model.predict(frame, device=0, conf=0.7, verbose=False, imgsz=640) # conf=0.7 확율 70% 이상만 탐지
            boxes = results[0].boxes  # results 정의 후 할당해야 에러가 안 납니다.
            

            # 3. 결과 렌더링 (바운딩 박스 그리기)
            annotated_frame = results[0].plot() 
            
            # 4. 웹 전송용 이미지 인코딩 (한 번만 수행)
            _, buffer = cv2.imencode('.jpg', annotated_frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            encoded_image = base64.b64encode(buffer).decode('utf-8')

            # 5. 프레임 송출
            socketio.emit('ai_frame', {
                'image': encoded_image,
                'count': frame_count
            })

            # 6. 특정 타겟 Alert 체크
            if cls._target_label:
                detected_names = [model.names[int(cls_idx)].lower() for cls_idx in boxes.cls.tolist()]
                if cls._target_label in detected_names:
                    socketio.emit('detection_alert', {
                        'label': cls._target_label,
                        'time': time.strftime('%H:%M:%S')
                    })
            
            # CPU/GPU 과열 방지
            socketio.sleep(0.01)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        cap.release()