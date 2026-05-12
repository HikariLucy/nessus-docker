# Nessus Docker - Persistencia Dual
Proyecto para la asignatura de Tecnologías de Virtualización.

## Requisitos
- Docker Desktop
- Docker Compose

## Despliegue rápido
1. Clonar el repositorio.
2. Ejecutar: `docker compose up -d`

## Estrategia de Persistencia
Usa un Named Volume para datos críticos y un Bind Mount para logs[cite: 178].