import fs from 'node:fs';
import path from 'node:path';

const ROOT = 'C:/CodingProjekte/PadelYara';

// --- read key from .env (no printing) ---
const env = fs.readFileSync(path.join(ROOT, '.env'), 'utf8');
const key = (env.split(/\r?\n/).find(l => l.startsWith('GEMINI_API_KEY=')) || '')
  .slice('GEMINI_API_KEY='.length).trim();
if (!key) { console.error('NO KEY'); process.exit(1); }

// --- reference photo to keep Yara consistent ---
const refPath = path.join(ROOT, 'brand/photos/Yaranobackground.png');
const refB64 = fs.readFileSync(refPath).toString('base64');

const model = 'gemini-2.5-flash-image'; // cheap validation pass
const prompt = `Create a vertical (portrait) cinematic advertising photograph.
Use the cat in the reference image — keep its appearance IDENTICAL (same black short-haired cat, same yellow-green eyes).
Scene: the cat sits regally on the glass-and-metal railing of a rooftop padel court at dusk. Dramatic sunset sky (deep blue fading to orange), blurred city-skyline bokeh lights in the distance, a tall stadium floodlight glowing on the right, the blue padel court faintly visible below. Moody, premium, high-end ad photography, sharp focus on the cat, shallow depth of field. The cat looks directly at the camera.
Keep the LEFT side of the frame darker and uncluttered for text overlay later. Absolutely NO text, NO logos, NO watermarks in the image.`;

const body = {
  contents: [{ role: 'user', parts: [
    { inlineData: { mimeType: 'image/png', data: refB64 } },
    { text: prompt },
  ] }],
  generationConfig: { responseModalities: ['IMAGE'] },
};

console.log('Generating with', model, '...');
const res = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent`, {
  method: 'POST',
  headers: { 'x-goog-api-key': key, 'content-type': 'application/json' },
  body: JSON.stringify(body),
});
if (!res.ok) { console.error('HTTP', res.status, (await res.text()).slice(0, 800)); process.exit(1); }
const data = await res.json();
const parts = data?.candidates?.[0]?.content?.parts || [];
const img = parts.find(p => p.inlineData);
if (!img) { console.error('NO IMAGE. Response:', JSON.stringify(data).slice(0, 800)); process.exit(1); }

const outDir = path.join(ROOT, 'scripts/yara-post/out');
fs.mkdirSync(outDir, { recursive: true });
const outPath = path.join(outDir, 'test-scene.png');
fs.writeFileSync(outPath, Buffer.from(img.inlineData.data, 'base64'));
console.log('SAVED', outPath, '-', fs.statSync(outPath).size, 'bytes');
