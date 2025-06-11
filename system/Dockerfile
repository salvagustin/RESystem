# Usa una imagen oficial de Python
FROM python:3.11-slim

# Establece el directorio de trabajo
WORKDIR /system

# Copia todo el contenido del proyecto (excepto lo que esté en .dockerignore)
COPY . .

# Instala dependencias
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Expone el puerto donde correrá Gunicorn
EXPOSE 8080

# Comando para ejecutar tu app
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "system.wsgi"]
