FROM python:alpine
RUN apk update
RUN apk --no-cache add curl
RUN pip install --upgrade pip
COPY requirements.txt /opt/app/requirements.txt
WORKDIR /opt/app
RUN pip install -r requirements.txt
COPY api.py /opt/app/api.py
RUN chmod +x /opt/app/api.py
ENTRYPOINT ["python", "api.py"]