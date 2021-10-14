FROM python:3.10.0-slim

WORKDIR /app
COPY . .
RUN pip3 install -r requirements.txt

CMD ["gunicorn"  , "-b", "0.0.0.0:5000", "application:application"]
