'use strict';
const fs = require('node:fs');
const path = require('node:path');
const { Client, LocalAuth } = require('whatsapp-web.js');
const qr = require('qrcode-terminal');
const root = path.resolve(__dirname, '..');
const command = process.argv[2] || 'link';
if (!['link', 'groups', 'send'].includes(command)) throw new Error('Usa link, groups o send');
const configPath = path.resolve(process.argv[3] || path.join(root, 'config.json'));
const config = JSON.parse(fs.readFileSync(configPath, 'utf8'));
const sessionPath = path.join(root, 'data', 'wa-session');
fs.mkdirSync(sessionPath, {recursive: true, mode: 0o700});
let client;
let closing = false;
let busy = false;
async function close(code) {
  if (closing) return;
  closing = true;
  try { await client.destroy(); } catch (_) {}
  process.exit(code);
}
let watchdog = setTimeout(() => { console.error('Tiempo agotado vinculando WhatsApp'); close(1); }, 180000);
client = new Client({
  authStrategy: new LocalAuth({dataPath: sessionPath}),
  puppeteer: {headless: true}
});
client.on('qr', code => {
  if (command === 'send') {
    console.error('Sesión caducada: ejecuta primero npm run link');
    close(1);
  } else {
    console.error('Escanea el QR desde Dispositivos vinculados. No lo compartas.');
    qr.generate(code, {small: true});
  }
});
client.on('auth_failure', () => { console.error('Fallo de autenticación'); close(1); });
client.on('disconnected', () => { console.error('WhatsApp desconectado'); close(1); });
client.on('ready', async () => {
  clearTimeout(watchdog);
  watchdog = setTimeout(() => { console.error('Tiempo agotado'); close(1); }, 180000);
  try {
    if (command === 'link') {
      console.log('Cuenta vinculada. No se ha enviado ningún mensaje.');
      return close(0);
    }
    if (command === 'groups') {
      const chats = await client.getChats();
      console.log(JSON.stringify(chats.filter(c => c.isGroup).map(c => ({name: c.name, id: c.id._serialized})), null, 2));
      return close(0);
    }
    let input = '';
    for await (const chunk of process.stdin) {
      input += chunk;
      if (Buffer.byteLength(input) > 32768) throw new Error('Entrada demasiado grande');
    }
    const payload = JSON.parse(input);
    const allowed = config.whatsapp.groups;
    if (!['A', 'B'].includes(payload.group) || !allowed[payload.group]) throw new Error('Grupo A/B no configurado');
    const target = allowed[payload.group];
    if (typeof target !== 'string' || !target.endsWith('@g.us')) throw new Error('ID de grupo inválido');
    if (typeof payload.text !== 'string' || !payload.text.trim() || payload.text.length > 4000) throw new Error('Texto vacío o demasiado largo');
    const chat = await client.getChatById(target);
    if (!chat.isGroup) throw new Error('El destino no es un grupo');
    busy = true;
    const sent = await client.sendMessage(target, payload.text);
    busy = false;
    console.log(JSON.stringify({sent: true, message_id: sent.id._serialized}));
    await close(0);
  } catch (error) {
    console.error('Error del puente:', error.message);
    if (busy) console.error('Resultado incierto: revisa el grupo antes de repetir el envío.');
    await close(1);
  }
});
process.on('SIGINT', () => close(130));
process.on('SIGTERM', () => close(143));
client.initialize().catch(() => { console.error('No se pudo iniciar Chromium/WhatsApp'); close(1); });
