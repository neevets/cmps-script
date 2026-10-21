# Modo exclusivo SMX A/B (v2)

Esta versión reemplaza main.py. Los módulos antiguos de CallMeBot permanecen por historial, pero el nuevo ejecutable NO los utiliza. Configuración JSON nueva: copia config.example.json a config.json y protege el archivo (chmod 600). No subas cookies ni tokens.

## Estado y límites

Implementación inicial sin validar contra HTML autenticado real del instituto. Las capturas no permiten probar selectores. No se promete cobertura completa: páginas cargadas mediante JavaScript, secciones colapsadas sin contenido HTML, anuncios enlazados y documentos externos pueden requerir adaptación. Solo lee HTML autorizado; no abre actividades bloqueadas. No descarga imágenes ni aplica OCR.

Lee /my/courses.php para descubrir cursos. Si Moodle no publica los enlaces en el HTML inicial, añade sus URLs completas a moodle.course_urls. Se rechazan URLs fuera del Moodle configurado. Caducidad de sesión/redirecciones producen error, no un falso resultado vacío.

Extrae Venciment/Fecha de entrega/Due y anuncios de examen/prova con líneas de grupo y fecha. Catalán con año explícito y fechas dd/mm/yyyy. Si falta el año, registra un candidato sin enviar. No inventa año ni hora. Fechas sin hora: ventana de dos días naturales. Fechas con hora: próximas 48 horas. No confunde A1/A2 con Grup A. No excluye tareas por Feta: es el estado personal, no el del grupo. Datos ambiguos no se envían.

Para actividades sin grupo explícito configura course_groups, usando URL exacta del curso como clave y ["A"] o ["B"] como valor. ["A", "B"] es ambiguo y no genera envío automático. La asignación explícita tiene prioridad. Cada anuncio con líneas separadas A y B produce candidatos independientes. No se envía a Avisos/General ni a números individuales.

## Prueba

pip install -r requirements.txt
python main.py

Por defecto solo registra candidatos y no marca entregas. No se han realizado pruebas end-to-end con Moodle/WhatsApp. Inspecciona candidatos antes de activar --send. Se necesitan HTML reales sin secretos para validar selectores y añadir fixtures.

## Puente de WhatsApp requerido (NO incluido)

Este commit NO contiene un servidor WhatsApp ni vincula un número. Necesitas implementar o configurar un servicio que realmente pueda publicar en tus grupos existentes con una cuenta autorizada. No basta con poner la URL de CallMeBot/Twilio. No hay credenciales ni IDs reales incluidos.

Contrato de webhook: POST HTTPS, Authorization: Bearer <token>, JSON {group_id, text, idempotency_key}. Debe devolver JSON {"sent": true} solamente tras confirmar envío. El puente debe deduplicar idempotency_key, validar destinos y proteger su autenticación. Ante timeout no se registra entrega; la idempotencia del puente evita repetir un envío ya aceptado. La base local guarda confirmaciones por actividad, grupo y fecha. Cambios en esos datos generan nuevo aviso.

Una vez configurado y validado:
python main.py --send

Cron cada 12 h (ajusta rutas, permisos y zona horaria del VPS):
0 8,20 * * * cd /opt/cmps-script && /opt/cmps-script/.venv/bin/python main.py --send >> /opt/cmps-script/data/bot.log 2>&1

No actives simultáneamente varios procesos. Conserva data/ entre ejecuciones. Si no tienes un puente, usa solo modo prueba: todavía NO habrá mensajes en los grupos.
