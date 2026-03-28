FROM python:3.9

WORKDIR /app

COPY ../backend /app

RUN pip install flask

EXPOSE 5001

CMD ["python", "app.py"]
