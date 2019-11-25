FROM python:3.6-slim
MAINTAINER Suvarchal K. Cheedela <suvarchal.kumar@gmail.com>

ENV INSTALL_PATH /app
RUN mkdir -p $INSTALL_PATH
WORKDIR $INSTALL_PATH

COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

EXPOSE 8000
#CMD gunicorn -b 0.0.0.0:8000 --access-logfile - "app.teleport_app:create_app()"

