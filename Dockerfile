FROM tiangolo/uwsgi-nginx-flask:python3.9

ENV UWSGI_INI /app/uwsgi.ini
ENV LISTEN_PORT 5000

COPY ./requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /app/requirements.txt

EXPOSE 5000

WORKDIR /app
COPY ./ /app