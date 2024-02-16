FROM python:3.12-slim
RUN apt-get update
RUN apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*
RUN pip install --upgrade pip
COPY requirements.txt /opt/app/requirements.txt
WORKDIR /opt/app
RUN pip install -r requirements.txt
RUN python -m spacy download en_core_web_lg
COPY entity.py /opt/app/entity.py
RUN chmod +x /opt/app/entity.py
ENTRYPOINT ["python", "entity.py"]