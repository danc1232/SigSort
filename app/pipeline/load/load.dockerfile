FROM python:alpine
RUN apk update
RUN pip install --upgrade pip
COPY requirements.txt /opt/app/requirements.txt
WORKDIR /opt/app
RUN pip install -r requirements.txt
COPY load.py /opt/app/load.py
RUN chmod +x /opt/app/load.py
ENTRYPOINT ["python", "load.py"]