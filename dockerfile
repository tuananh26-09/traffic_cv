# File dockerfile của bạn nên trông như thế này
FROM python:3.10-slim
WORKDIR /src

RUN apt-get update && apt-get install -y libgl1 libglib2.0-0

COPY requirement.txt .
RUN pip install --upgrade pip
RUN pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r requirement.txt

COPY . .

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]