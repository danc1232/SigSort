FROM python:alpine
RUN apk update
RUN pip install --upgrade pip
COPY requirements.txt /opt/app/requirements.txt
WORKDIR /opt/app
RUN pip install -r requirements.txt
COPY keyextract.py /opt/app/keyextract.py
RUN chmod +x /opt/app/keyextract.py
ENTRYPOINT ["python", "keyextract.py"]