FROM eclipse-temurin:17

WORKDIR /app

COPY templates/java /app

RUN javac app.java

EXPOSE 8082

CMD ["java", "app"]
