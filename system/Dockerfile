# Usa una imagen oficial de Python
FROM python:3.11-slim

WORKDIR /system

COPY . .

RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Recoge archivos estáticos (opcional, si usas WhiteNoise)
RUN python manage.py collectstatic --noinput

EXPOSE 8080

CMD ["gunicorn", "--bind", "0.0.0.0:8080", "system.wsgi"]
