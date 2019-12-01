FROM python:3.6-slim
MAINTAINER Suvarchal K. Cheedela <suvarchal.kumar@gmail.com>

COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

ENV INSTALL_PATH /app
RUN mkdir -p $INSTALL_PATH
WORKDIR $INSTALL_PATH

#set user from compose
#RUN chown 1000:133 $INSTALL_PATH
#USER 1000:133
EXPOSE 5000
CMD gunicorn -b 0.0.0.0:5000 teleport_app:app

