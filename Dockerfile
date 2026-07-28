FROM python:3.11-slim

COPY requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt

COPY . /action
WORKDIR /action

ENTRYPOINT ["python", "/action/main.py"]
