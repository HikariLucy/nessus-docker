# Imagen base oficial de Prometheus
FROM prom/prometheus:latest

# Metadatos de la imagen
LABEL maintainer="Jesús Quijada"
LABEL version="1.0.0"
LABEL description="Imagen de Prometheus para monitoreo de HealthTrack con persistencia dual"

# Declarar los volúmenes de datos y configuración
VOLUME ["/prometheus", "/etc/prometheus"]

# Exponer el puerto por defecto de Prometheus
EXPOSE 9090