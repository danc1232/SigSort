FROM python:alpine
RUN apk update
RUN pip install --upgrade pip
RUN apk add --no-cache gcc
COPY requirements.txt /opt/app/requirements.txt
WORKDIR /opt/app
RUN pip install -r requirements.txt
COPY ingest.py /opt/app/ingest.py
RUN chmod +x /opt/app/ingest.py
ENTRYPOINT ["python", "ingest.py"]