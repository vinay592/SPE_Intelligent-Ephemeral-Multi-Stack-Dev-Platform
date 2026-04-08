FROM eclipse-temurin:17

RUN apt update && apt install -y python3 python3-pip

RUN pip install flask --break-system-packages

WORKDIR /app

COPY . .

EXPOSE 8082

CMD ["python3", "app.py"]
