# CMPS Script — Exámenes de Moodle a WhatsApp

Lee tus cursos de Moodle y avisa por WhatsApp, en los grupos SMX (A) y SMX (B), de los exámenes (y opcionalmente tareas) con fecha en las próximas 48 horas. No repite avisos (SQLite).

Flujo: `main.py` (Python, lee Moodle) → `bridge/bridge.cjs` (Node, WhatsApp Web por QR) → grupo.

> El puente QR no es oficial: puede dejar de funcionar o tener restricciones de cuenta. Úsalo solo con una cuenta tuya y grupos cuyos miembros acepten los avisos.

## Instalación (en un PC o VPS siempre encendido, Node 20+)

```bash
git clone https://github.com/neevets/cmps-script.git && cd cmps-script
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp config.example.json config.json && chmod 600 config.json
cd bridge && npm install
```

1. Pon tu cookie `MoodleSession` en `config.json` (`moodle.cookie`). Caduca: si el bot dice "Sesión no válida", renuévala.
2. `npm run link` (en `bridge/`) y escanea el QR en WhatsApp → Dispositivos vinculados.
3. `npm run groups` y copia los IDs de SMX (A) y SMX (B) en `whatsapp.groups.A` / `.B`.
4. Para cursos sin "Grupo A/B" en el texto, asigna `course_groups` (URL exacta del curso → `["A"]`, `["B"]` o `["A","B"]` para ambos).

## Uso

```bash
python main.py          # prueba: muestra lo que enviaría
python main.py --send   # envía de verdad
```

Automático cada 12 h:

```cron
0 8,20 * * * cd /opt/cmps-script && /opt/cmps-script/.venv/bin/python main.py --send >> /opt/cmps-script/data/bot.log 2>&1
```

`only_exams: true` (por defecto) envía solo exámenes/cuestionarios; ponlo a `false` para incluir tareas.
Si WhatsApp no confirma un envío, se registra un error y no se repite (revisa el grupo). Tests: `pip install pytest && pytest`.

Más detalles en `GROUPS.md` y `QR.md`. No subas `config.json`, cookies ni `data/`.
