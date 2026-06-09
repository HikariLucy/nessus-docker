# Evaluación Parcial N°2 — Despliegue de Prometheus con Docker Compose y AWS ECS

**INY1105 — Infraestructura de Aplicaciones I**  
DuocUC · Escuela de Informática y Telecomunicaciones · 2026/1

---

## Instrucciones

### 1. Crea tu propio repositorio desde este template

1. Haz clic en el botón **"Use this template"** → **"Create a new repository"**
2. En el campo **Repository name** escribe: `iny1105-ea2-nombre-apellido` (usa tu nombre real)
3. Selecciona **Private**
4. Haz clic en **"Create repository"**

> **Importante:** El repositorio debe quedar en **tu cuenta personal** de GitHub, no en la cuenta del curso.  
> El nombre debe seguir el formato `iny1105-ea2-nombre-apellido` exactamente.

---

### 2. Clona tu repositorio y comienza a trabajar

```bash
git clone https://github.com/tu-usuario/iny1105-ea2-nombre-apellido.git
cd iny1105-ea2-nombre-apellido
```

---

### 3. Estructura del proyecto

```
iny1105-ea2-nombre-apellido/
├── Dockerfile             ← completar: FROM, LABEL, VOLUME, EXPOSE
├── docker-compose.yml     ← completar: Named Volume, Bind Mount y variable de entorno
├── config/
│   └── prometheus.yml     ← archivo de configuración base (ya configurado, no modificar)
├── .dockerignore          ← ya configurado
├── .gitignore             ← ya configurado
└── README.md              ← completar con instrucciones de uso
```

---

### 4. Flujo de trabajo

```
[1] Completar Dockerfile y docker-compose.yml
        ↓
[2] Validar localmente con Docker Compose
        ↓
[3] Publicar imagen en Amazon ECR
        ↓
[4] Desplegar en AWS ECS Fargate
        ↓
[5] Hacer push de tus cambios a GitHub con las evidencias
```

---

### 5. Comandos de validación local

```bash
# Construir la imagen
docker compose build

# Iniciar el servicio
docker compose up -d

# Verificar que está corriendo
docker compose ps

# Revisar logs en tiempo real
docker compose logs -f prometheus

# Verificar el Bind Mount (debe aparecer prometheus.yml)
ls -la ./config/

# Inspeccionar el Named Volume
docker volume inspect $(basename $(pwd))_prometheus_data
```

Accede a Prometheus en: **http://localhost:9090**

---

### 6. Entregables en este repositorio

Al finalizar, tu repositorio debe contener:

| # | Archivo | Descripción |
|---|---|---|
| 1 | `Dockerfile` | Completado con FROM, LABEL, VOLUME y EXPOSE |
| 2 | `docker-compose.yml` | Completado con Named Volume, Bind Mount y variable de entorno |
| 3 | `README.md` | Completado con instrucciones de uso y variables de entorno |

Las capturas de pantalla (evidencias) van en el **reporte técnico PDF** que se sube al AVA.

---

### 7. Subir tu trabajo

```bash
# Agregar todos los cambios
git add .
git commit -m "feat: Prometheus containerizado con persistencia dual - Nombre Apellido"

# Subir a tu repositorio
git push origin main
```

Luego, en el AVA:
1. Adjunta tu **reporte técnico en PDF**
2. Pega la **URL de tu repositorio GitHub** en el campo de texto de la tarea

---

*Docente: Rodrigo Aguilar G. — r.aguilarg@profesor.duoc.cl*

# Evaluación Parcial N°2 — Despliegue de Prometheus con Docker Compose y AWS ECS

* **Asignatura:** Tecnologías de Virtualización (DIY7111)
* **Estudiante:** Jesús Ignacio Quijada Molina
* **Institución:** DuocUC — Escuela de Informática y Telecomunicaciones
* **Docente:** Rodrigo Aguilar G.

---

## Descripción del Proyecto
Este repositorio contiene la solución para la Evaluación Parcial N°2. Consiste en la containerización, configuración y despliegue de un servidor de monitoreo **Prometheus** enfocado en el cumplimiento de alta disponibilidad y persistencia de datos (Persistencia Dual) para la aplicación HealthTrack. 

El proyecto incluye la configuración del entorno local mediante Docker Compose y el posterior despliegue cloud serverless utilizando los servicios **Amazon ECR** y **AWS ECS Fargate**.

---

## Requisitos de Persistencia Implementados
Para garantizar que las métricas y configuraciones no se pierdan al destruir los contenedores, se aplicó una estrategia de **Persistencia Dual**:
1. **Named Volume (`prometheus_data`):** Montado en `/prometheus` para almacenar y persistir la base de datos de métricas en formato de series temporales (TSDB).
2. **Bind Mount:** Montado en `/etc/prometheus/prometheus.yml` apuntando al directorio local `./config/prometheus.yml` para permitir modificaciones dinámicas de la configuración de monitoreo desde el host.

---

## Variables de Entorno Configuradas
El servicio cuenta con las siguientes variables de entorno clave:
* `TZ=America/Santiago`: Define la zona horaria del contenedor para la correcta sincronización de las alertas y métricas.
* `APP_ENV=production`: Define el entorno de ejecución de la aplicación como "producción".

---

## Instrucciones de Uso Local

### 1. Construir e iniciar los contenedores
Ejecute el siguiente comando en la raíz del proyecto para compilar la imagen personalizada y levantar el entorno en segundo plano:
```bash
docker compose build
docker compose up -d