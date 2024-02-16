FROM python:alpine
RUN apk update
RUN pip install --upgrade pip
COPY requirements.txt /opt/app/requirements.txt
WORKDIR /opt/app
RUN pip install -r requirements.txt
COPY cve.py /opt/app/cve.py
RUN chmod +x /opt/app/cve.py
ENTRYPOINT ["python", "cve.py"]