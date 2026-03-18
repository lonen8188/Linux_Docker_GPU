FROM python:3.11

WORKDIR /app

# 1. OS 패키지
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# 2. requirements 먼저 복사
COPY requirements.txt .

# 3. torch (무거운거 먼저, 캐시 유지)
RUN pip install torch==2.0.1+cu118 torchvision==0.15.2+cu118 \
    --index-url https://download.pytorch.org/whl/cu118

# 4. 나머지 설치
RUN pip install --no-cache-dir -r requirements.txt

# 5. 코드 복사 (여기 변경돼도 pip 안 다시 깔림)
COPY . .

ENV PYTHONPATH=/app

CMD ["python", "LMS/app.py"]