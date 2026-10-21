# WhatsApp por QR: puente local

Puente Node.js inicial. No oficial: puede dejar de funcionar o provocar restricciones de cuenta. Solo úsalo con una cuenta autorizada y grupos cuyos miembros acepten estos avisos. GitHub Pages no puede ejecutarlo. Este commit no despliega ningún servicio ni integra aún automáticamente el lector Python: main.py sigue usando el webhook anterior. No actives el cron esperando que utilice este puente.

## Requisitos

Node.js 20 o posterior y dependencias de Chromium/Puppeteer compatibles con tu sistema. Ejecuta como usuario normal, no root; no se desactiva el sandbox. Python y sus dependencias se mantienen para Moodle. Guarda sesiones y SQLite en disco persistente. No uses dos procesos del puente simultáneamente.

## Vincular

Desde la raíz del repo, crea config.json a partir de config.example.json si aún no existe. Conserva tu configuración real, no la publiques.

cd bridge
npm install
npm run link

En WhatsApp abre Dispositivos vinculados y escanea el QR mostrado en tu terminal privada. La vinculación no envía mensajes. No compartas QR ni archivos de sesión. Estos últimos quedan en data/wa-session, excluido del Git por la regla data/ existente.

## Identificar destinos

npm run groups

Copia únicamente los IDs correspondientes a SMX (A) y SMX (B) en whatsapp.groups.A y whatsapp.groups.B de config.json. Comprueba los nombres y sus IDs; no se eligen por coincidencias parciales. No publiques el listado de grupos.

## Envío manual explícito

Desde bridge/, un mensaje de prueba solo si quieres publicarlo realmente:

printf '%s' '{"group":"B","text":"Prueba del bot de Moodle"}' | node bridge.cjs send

Solo permite los IDs A/B de config.json. No acepta destinatarios arbitrarios ni publica en Avisos/General. Publica texto normal, no menciona automáticamente a todos. El éxito indica aceptación de la operación por la biblioteca, no lectura por los participantes. Si hay timeout durante un envío, revisa el chat antes de reintentar para evitar duplicados.

## Pendiente antes de automatizar

Conectar Python al comando send, corregir/validar fechas catalanas con los HTML recibidos, permitir tareas comunes de Redes a ambos grupos y añadir pruebas de extracción/cambios. No se han ejecutado pruebas end-to-end ni vinculado ninguna cuenta durante la creación del código. El script se cierra tras cada operación; no es un servidor público ni requiere dominio, token webhook o puertos abiertos.
