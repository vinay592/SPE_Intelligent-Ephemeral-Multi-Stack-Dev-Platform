FROM python:3.9

WORKDIR /app

COPY templates/ml /app

RUN pip install -r requirements.txt

EXPOSE 8888

CMD ["python", "app.py"]
