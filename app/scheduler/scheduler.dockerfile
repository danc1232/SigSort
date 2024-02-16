FROM python:alpine
RUN apk update
RUN pip install --upgrade pip
COPY requirements.txt /opt/app/requirements.txt
WORKDIR /opt/app
RUN pip install -r requirements.txt
COPY scheduler.py /opt/app/scheduler.py
RUN chmod +x /opt/app/scheduler.py
ENTRYPOINT ["python", "scheduler.py"]