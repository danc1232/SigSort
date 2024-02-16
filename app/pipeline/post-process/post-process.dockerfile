FROM python:alpine
RUN apk update
RUN pip install --upgrade pip
COPY requirements.txt /opt/app/requirements.txt
WORKDIR /opt/app
RUN pip install -r requirements.txt
COPY post-process.py /opt/app/post-process.py
RUN chmod +x /opt/app/post-process.py
ENTRYPOINT ["python", "post-process.py"]