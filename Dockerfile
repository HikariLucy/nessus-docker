# Imagen base recomendada por ser ligera y compatible [cite: 280, 631]
FROM debian:bookworm-slim

# Metadatos obligatorios [cite: 281, 282, 283]
LABEL maintainer="tu-usuario@correo.com"
LABEL version="1.0.0"
LABEL description="Tenable Nessus containerizado para INY1105"

# Evita prompts interactivos durante la instalación [cite: 284, 632]
ENV DEBIAN_FRONTEND=noninteractive
ENV NESSUS_VERSION="10.12.0"
ENV NESSUS_PACKAGE="Nessus-${NESSUS_VERSION}-debian10_amd64.deb"

# Instalación de dependencias y limpieza de caché en una sola capa [cite: 287, 293, 634]
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    libssl3 \
    ca-certificates \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Descarga, instalación y borrado del temporal en la misma capa [cite: 294, 298, 299, 635]
RUN wget -q "https://www.tenable.com/downloads/api/v2/pages/nessus/files/${NESSUS_PACKAGE}" -O /tmp/${NESSUS_PACKAGE} \
    && dpkg -i /tmp/${NESSUS_PACKAGE} \
    && rm -f /tmp/${NESSUS_PACKAGE}

# Definición de volúmenes para persistencia dual [cite: 300, 636]
VOLUME ["/opt/nessus", "/opt/nessus/var/nessus/logs"]

# Exposición del puerto oficial [cite: 301, 637]
EXPOSE 8834

# Comando de inicio del servicio [cite: 302, 638]
CMD ["/bin/bash", "-c", "/opt/nessus/sbin/nessus-service -D && tail -f /dev/null"]