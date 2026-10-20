// Writes the Workshop upload's workshop.txt description from main_en.txt (node make_workshop_txt.js).
// Until the add-on is uploaded (ADDON_URL / IMG_WRAITH_BRIEFING still placeholders) its name is
// left as plain text and its picture is left out, so the file can be uploaded at any time.
const fs = require('fs');
const path = require('path');
const target = 'C:/Users/user/Zomboid/Workshop/SkyhammerAirSupport/workshop.txt';
let body = fs.readFileSync(path.join(__dirname, 'main_en.txt'), 'utf8').replace(/\r\n/g, '\n').replace(/\n+$/, '');
body = body.replace(/\[url=ADDON_URL\]([^\[]*)\[\/url\]/g, '$1').replace(/^\[img\]IMG_[A-Z_]+\[\/img\]\n/gm, '');
const left = body.match(/ADDON_URL|IMG_[A-Z_]+/g);
if (left) throw new Error('placeholders left: ' + left.join(', '));
const old = fs.readFileSync(target, 'utf8').replace(/\r\n/g, '\n').split('\n');
const head = old.filter(l => /^(version|id|title)=/.test(l));
const tail = old.filter(l => /^(tags|visibility)=/.test(l));
const out = [...head, ...body.split('\n').map(l => 'description=' + l), ...tail].join('\r\n') + '\r\n';
fs.writeFileSync(target, out);
console.log('workshop.txt: ' + body.split('\n').length + ' description lines');
