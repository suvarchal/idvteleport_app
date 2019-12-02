FROM python:3.6-slim
MAINTAINER Suvarchal K. Cheedela <suvarchal.kumar@gmail.com>

COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

RUN mkdir -p /app
COPY ./app/settings.py /app/settings.py 
COPY ./app/teleport_app.py /app/teleport_app.py
COPY ./app/teleport_worker.py /app/teleport_worker.py
COPY ./app/templates /app/templates
WORKDIR /app

#set user from compose
#RUN chown 1000:133 $INSTALL_PATH
#USER 1000:133
EXPOSE 5000
#CMD gunicorn -b 0.0.0.0:5000 teleport_app:app

