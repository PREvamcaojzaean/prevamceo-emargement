from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from PIL import Image
import base64, io, os, json, uuid, time

app = Flask(__name__)
CORS(app)

W, H = A4
SESSIONS_DIR = '/tmp/prevamceo_sessions'
SIGNATURES_DIR = '/tmp/prevamceo_signatures'
os.makedirs(SESSIONS_DIR, exist_ok=True)
os.makedirs(SIGNATURES_DIR, exist_ok=True)

def get_session_path(session_id):
    return os.path.join(SESSIONS_DIR, f'{session_id}.json')

def get_sig_path(session_id, nom, prenom):
    key = f"{session_id}_{nom}_{prenom}".replace(' ', '_')
    return os.path.join(SIGNATURES_DIR, f'{key}.json')

def load_session(session_id):
    path = get_session_path(session_id)
    if not os.path.exists(path):
        return None
    with open(path, 'r') as f:
        return json.load(f)

def save_session(session_id, data):
    path = get_session_path(session_id)
    with open(path, 'w') as f:
        json.dump(data, f)

def load_signature(session_id, nom, prenom):
    """Charge UNIQUEMENT la signature stockée pour ce session_id précis.
    Pas de fallback vers d'autres sources — évite tout mélange entre formations."""
    path = get_sig_path(session_id, nom, prenom)
    if not os.path.exists(path):
        return None
    with open(path, 'r') as f:
        return json.load(f).get('signature')

def save_signature(session_id, nom, prenom, signature):
    path = get_sig_path(session_id, nom, prenom)
    with open(path, 'w') as f:
        json.dump({'signature': signature}, f)

def b64_to_image(b64_str):
    if not b64_str:
        return None
    if ',' in b64_str:
        b64_str = b64_str.split(',')[1]
    img_data = base64.b64decode(b64_str)
    return Image.open(io.BytesIO(img_data)).convert('RGBA')

def dessiner_signature(c, b64_str, x, y, w, h):
    try:
        sig_img = b64_to_image(b64_str)
        if sig_img:
            sig_buffer = io.BytesIO()
            sig_img.save(sig_buffer, format='PNG')
            sig_buffer.seek(0)
            img_reader = ImageReader(sig_buffer)
            c.drawImage(img_reader, x, y, width=w, height=h,
                       preserveAspectRatio=True, mask='auto')
            return True
    except Exception as e:
        print(f"Erreur signature: {e}")
    return False

def generer_pdf(data, sig_formateur=None, session_id=None):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    mL, mR, mT = 18*mm, 18*mm, 15*mm
    cW = W - mL - mR

    # ===== HEADER =====
    c.setStrokeColorRGB(0.1, 0.23, 0.36)
    c.setFillColorRGB(0.1, 0.23, 0.36)
    c.rect(mL, H - mT - 22*mm, cW, 22*mm, stroke=0, fill=1)

    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(mL + 5*mm, H - mT - 14*mm, "PRÉVAMCEO")
    c.setFont("Helvetica", 9)
    c.drawString(mL + 5*mm, H - mT - 20*mm, "Feuille de présence numérique")

    c.setFont("Helvetica", 8)
    c.drawRightString(W - mR - 5*mm, H - mT - 10*mm, "Enregistrement EQ003")
    c.drawRightString(W - mR - 5*mm, H - mT - 16*mm, "Version 2")

    # ===== INFOS FORMATION =====
    y = H - mT - 28*mm

    c.setStrokeColorRGB(0.88, 0.89, 0.91)
    c.setLineWidth(0.5)

    def info_ligne(label, valeur, yp):
        c.setFillColorRGB(0.4, 0.4, 0.4)
        c.setFont("Helvetica-Bold", 8)
        c.drawString(mL, yp, label.upper())
        c.setFillColorRGB(0.1, 0.1, 0.1)
        c.setFont("Helvetica", 10)
        c.drawString(mL + 38*mm, yp, str(valeur) if valeur else '—')
        c.setStrokeColorRGB(0.88, 0.89, 0.91)
        c.setLineWidth(0.3)
        c.line(mL, yp - 1.5*mm, W - mR, yp - 1.5*mm)

    info_ligne("Formation", data.get('titre',''), y);            y -= 8*mm
    info_ligne("Client",    data.get('entreprise',''), y);       y -= 8*mm
    info_ligne("Session n°", data.get('session',''), y);         y -= 8*mm
    info_ligne("Date",      data.get('date',''), y);             y -= 8*mm
    info_ligne("Horaires",  data.get('horaires',''), y);         y -= 8*mm
    info_ligne("Lieu",      data.get('lieu', data.get('adresse','')), y); y -= 8*mm
    info_ligne("Formateur", data.get('formateur',''), y);        y -= 12*mm

    # ===== TITRE SECTION EMARGEMENT =====
    c.setFillColorRGB(0.1, 0.23, 0.36)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(mL, y, "Émargement des apprenants")
    c.setLineWidth(1)
    c.setStrokeColorRGB(0.1, 0.23, 0.36)
    c.line(mL, y - 2*mm, W - mR, y - 2*mm)
    y -= 8*mm

    # ===== LISTE PARTICIPANTS =====
    participants = data.get('participants', [])
    sig_h = 18*mm
    nom_col = 70*mm

    for i, p in enumerate(participants):
        nom = p.get('nom','').strip()
        prenom = p.get('prenom','').strip()
        if not nom and not prenom:
            continue

        if y - sig_h - 5*mm < 35*mm:
            c.showPage()
            y = H - mT - 15*mm

        if i % 2 == 0:
            c.setFillColorRGB(0.97, 0.98, 1.0)
            c.rect(mL - 2*mm, y - sig_h + 2*mm, cW + 4*mm, sig_h, stroke=0, fill=1)

        c.setFillColorRGB(0.1, 0.23, 0.36)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(mL, y - 3*mm, f"{i+1}.")

        c.setFillColorRGB(0.1, 0.1, 0.1)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(mL + 8*mm, y - 3*mm, f"{prenom} {nom}".strip())

        entreprise = p.get('entreprise','').strip()
        if entreprise:
            c.setFillColorRGB(0.5, 0.5, 0.5)
            c.setFont("Helvetica", 8)
            c.drawString(mL + 8*mm, y - 9*mm, entreprise)

        c.setFillColorRGB(0.4, 0.4, 0.4)
        c.setFont("Helvetica", 7)
        c.drawString(mL + nom_col, y - 3*mm, "SIGNATURE")

        sig_x = mL + nom_col
        sig_w = cW - nom_col
        c.setStrokeColorRGB(0.7, 0.7, 0.7)
        c.setLineWidth(0.5)
        c.roundRect(sig_x, y - sig_h + 3*mm, sig_w, sig_h - 6*mm, 3*mm, stroke=1, fill=0)

        # ===== CHERCHER SIGNATURE — UNIQUEMENT depuis ce session_id =====
        # Plus de fallback vers p.get('signature') qui pouvait contenir
        # une ancienne donnée provenant du Sheets / Array Aggregator.
        sig_b64 = None
        if session_id:
            sig_b64 = load_signature(session_id, nom, prenom)

        if sig_b64 and len(sig_b64) > 100:
            ok = dessiner_signature(c, sig_b64,
                sig_x + 2*mm, y - sig_h + 5*mm,
                sig_w - 4*mm, sig_h - 10*mm)
            if not ok:
                c.setFillColorRGB(0.5, 0.5, 0.5)
                c.setFont("Helvetica", 8)
                c.drawCentredString(sig_x + sig_w/2, y - sig_h/2, "Erreur signature")
        else:
            c.setFillColorRGB(0.75, 0.75, 0.75)
            c.setFont("Helvetica", 8)
            c.drawCentredString(sig_x + sig_w/2, y - sig_h/2 + 2*mm, "Non signé")

        c.setStrokeColorRGB(0.88, 0.88, 0.88)
        c.setLineWidth(0.3)
        c.line(mL, y - sig_h + 1*mm, W - mR, y - sig_h + 1*mm)

        y -= sig_h + 2*mm

    # ===== SECTION FORMATEUR =====
    if y - sig_h - 15*mm < 30*mm:
        c.showPage()
        y = H - mT - 15*mm

    y -= 8*mm
    c.setFillColorRGB(0.1, 0.23, 0.36)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(mL, y, "Signature du formateur")
    c.setLineWidth(1)
    c.setStrokeColorRGB(0.1, 0.23, 0.36)
    c.line(mL, y - 2*mm, W - mR, y - 2*mm)
    y -= 8*mm

    c.setFillColorRGB(0.1, 0.1, 0.1)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(mL, y - 3*mm, data.get('formateur',''))
    c.setFillColorRGB(0.5, 0.5, 0.5)
    c.setFont("Helvetica", 8)
    c.drawString(mL, y - 9*mm, "Par cette signature j'atteste avoir animé la formation ci-dessus")

    sig_x = mL + nom_col
    sig_w = cW - nom_col
    sig_h_f = 22*mm
    c.setStrokeColorRGB(0.1, 0.23, 0.36)
    c.setLineWidth(0.8)
    c.roundRect(sig_x, y - sig_h_f + 2*mm, sig_w, sig_h_f - 2*mm, 3*mm, stroke=1, fill=0)

    if sig_formateur and len(sig_formateur) > 100:
        dessiner_signature(c, sig_formateur,
            sig_x + 2*mm, y - sig_h_f + 4*mm,
            sig_w - 4*mm, sig_h_f - 8*mm)

    # ===== FOOTER =====
    c.setFont("Helvetica", 6)
    c.setFillColorRGB(0.5, 0.5, 0.5)
    fY = 12*mm
    c.line(mL, fY + 5*mm, W - mR, fY + 5*mm)
    c.drawCentredString(W/2, fY + 2*mm, "Les informations recueillies sont enregistrées dans un fichier informatisé par PREVAMCEO — jparnaud@prevamceo.fr")
    c.drawCentredString(W/2, fY - 1.5*mm, "Prévamcéo - 11 B allée de la Falaise - 13820 Ensuès-la-Redonne – 06 08 13 92 57 – contact@prevamceo.fr – Siret 939 109 252 00014")

    c.save()
    buffer.seek(0)
    return buffer

# ===== ROUTES =====

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'service': 'Prevamceo Emargement v6 - sans fallback signature'})

@app.route('/stocker-signature', methods=['POST'])
def stocker_signature():
    body = request.json
    session_id = body.get('session_id')
    nom = body.get('nom','').strip()
    prenom = body.get('prenom','').strip()
    signature = body.get('signature','')
    if not session_id or not signature:
        return jsonify({'success': False, 'error': 'Données manquantes'}), 400
    save_signature(session_id, nom, prenom, signature)
    return jsonify({'success': True, 'message': f'Signature de {prenom} {nom} stockée'})

@app.route('/creer-session', methods=['POST'])
def creer_session():
    data = request.json
    session_id = str(uuid.uuid4())[:8]
    save_session(session_id, {
        'data': data,
        'signature_formateur': None,
        'cree_le': time.time()
    })
    base_url = request.host_url.rstrip('/')
    lien_signature = f"{base_url}/signer/{session_id}"
    return jsonify({
        'session_id': session_id,
        'lien_signature': lien_signature,
        'message': 'Session créée'
    })

@app.route('/signer/<session_id>', methods=['GET'])
def page_signature(session_id):
    session = load_session(session_id)
    if not session:
        return "Session expirée ou introuvable.", 404
    data = session['data']
    formateur = data.get('formateur', 'Formateur')
    formation = data.get('titre', 'Formation')
    date = data.get('date', '')

    participants_prevus = data.get('participants', [])
    participants_signes = []
    for p in participants_prevus:
        nom = p.get('nom', '').strip()
        prenom = p.get('prenom', '').strip()
        if not nom and not prenom:
            continue
        sig = load_signature(session_id, nom, prenom)
        participants_signes.append({'nom': nom, 'prenom': prenom, 'signe': bool(sig)})

    dejavu = {(p['nom'], p['prenom']) for p in participants_signes}
    if os.path.exists(SIGNATURES_DIR):
        for fname in os.listdir(SIGNATURES_DIR):
            if not fname.startswith(session_id + '_'):
                continue
            reste = fname[len(session_id) + 1:-5]
            parts = reste.split('_')
            if len(parts) >= 2:
                nom_f = parts[0]
                prenom_f = '_'.join(parts[1:])
                if (nom_f, prenom_f) not in dejavu:
                    participants_signes.append({'nom': nom_f, 'prenom': prenom_f, 'signe': True})

    participants = participants_signes
    liste_html = ''.join([
        f"<div class='participant'>{'✅' if p['signe'] else '⏳'} {p.get('prenom','')} {p.get('nom','')}</div>"
        for p in participants
    ])
    nb_signes = len([p for p in participants if p['signe']])
    nb_total = len(participants)
    nb = nb_total
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>Signature Formateur — Prévamceo</title>
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: -apple-system, sans-serif; background: #f4f6f9; padding-bottom: 40px; }}
.top {{ background: #1a3a5c; padding: 16px 20px; }}
.top h1 {{ color: white; font-size: 15px; font-weight: 600; }}
.top p {{ color: rgba(255,255,255,0.7); font-size: 12px; }}
.card {{ margin: 16px; background: white; border-radius: 12px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
.card h2 {{ font-size: 14px; font-weight: 600; color: #1a3a5c; margin-bottom: 12px; padding-bottom: 8px; border-bottom: 1px solid #eee; }}
.info {{ font-size: 13px; color: #555; margin-bottom: 6px; }}
.participant {{ font-size: 13px; color: #1a6b4a; padding: 6px 0; border-bottom: 1px solid #f0f0f0; }}
.sig-wrap {{ border: 1.5px solid #ddd; border-radius: 10px; background: #fafafa; position: relative; overflow: hidden; }}
canvas {{ display: block; width: 100%; height: 130px; cursor: crosshair; touch-action: none; }}
.sig-hint {{ position: absolute; top: 50%; left: 50%; transform: translate(-50%,-50%); font-size: 13px; color: #bbb; pointer-events: none; }}
.sig-hint.hidden {{ display: none; }}
.btn-clear {{ font-size: 12px; color: #888; background: none; border: none; cursor: pointer; text-decoration: underline; padding: 4px; }}
.btn-submit {{ width: 100%; padding: 16px; background: #1a3a5c; color: white; border: none; border-radius: 12px; font-size: 16px; font-weight: 600; cursor: pointer; margin-top: 8px; }}
.btn-submit:disabled {{ background: #888; }}
.success {{ display: none; text-align: center; padding: 40px 20px; }}
.success .icon {{ font-size: 60px; margin-bottom: 16px; }}
.success h2 {{ color: #1a6b4a; font-size: 20px; }}
.msg {{ padding: 12px; border-radius: 8px; font-size: 13px; display: none; margin-bottom: 12px; background: #fff0f0; color: #a32d2d; }}
</style>
</head>
<body>
<div class="top">
  <h1>Prévamceo — Signature formateur</h1>
  <p>Feuille de présence numérique</p>
</div>
<div class="card" id="main-card">
  <h2>Informations de la formation</h2>
  <div class="info">📋 <strong>{formation}</strong></div>
  <div class="info">👤 Formateur : <strong>{formateur}</strong></div>
  <div class="info">📅 Date : <strong>{date}</strong></div>
  <br>
  <h2>Participants — {nb_signes} signé(s) sur {nb_total}</h2>
  {liste_html}
  <br>
  <div style="font-size:12px;font-weight:600;color:#666;text-transform:uppercase;letter-spacing:0.4px;margin-bottom:8px;">Votre signature *</div>
  <div class="sig-wrap">
    <canvas id="sig-canvas"></canvas>
    <div class="sig-hint" id="sig-hint">✍️ Signez ici avec le doigt</div>
  </div>
  <div style="display:flex;justify-content:flex-end;margin-top:4px;">
    <button class="btn-clear" onclick="clearSig()">Effacer</button>
  </div>
  <div class="msg" id="msg"></div>
  <button class="btn-submit" id="btn-submit" onclick="soumettre()">✅ Valider et générer le PDF</button>
</div>
<div class="success" id="success">
  <div class="icon">✅</div>
  <h2>Signature enregistrée !</h2>
  <p style="font-size:14px;color:#555;margin-top:8px;">Le document va être généré et envoyé.<br><br>
  <span style="font-size:12px;color:#aaa;">Prévamceo — www.prevamceo.fr</span></p>
</div>
<script>
const SESSION_ID = '{session_id}';
const canvas = document.getElementById('sig-canvas');
const ctx = canvas.getContext('2d');
let hasDrawn = false, drawing = false;
function resize() {{
  const w = canvas.offsetWidth;
  canvas.width = w * window.devicePixelRatio;
  canvas.height = 130 * window.devicePixelRatio;
  ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
  ctx.strokeStyle = '#1a3a5c'; ctx.lineWidth = 2; ctx.lineCap = 'round'; ctx.lineJoin = 'round';
}}
resize(); window.addEventListener('resize', resize);
const getPos = e => {{ const r=canvas.getBoundingClientRect(); const s=e.touches?e.touches[0]:e; return {{x:s.clientX-r.left,y:s.clientY-r.top}}; }};
canvas.addEventListener('mousedown', e => {{ drawing=true; const {{x,y}}=getPos(e); ctx.beginPath(); ctx.moveTo(x,y); }});
canvas.addEventListener('mousemove', e => {{ if(!drawing)return; hasDrawn=true; document.getElementById('sig-hint').classList.add('hidden'); const {{x,y}}=getPos(e); ctx.lineTo(x,y); ctx.stroke(); }});
canvas.addEventListener('mouseup', ()=>drawing=false);
canvas.addEventListener('mouseleave', ()=>drawing=false);
canvas.addEventListener('touchstart', e=>{{e.preventDefault();drawing=true;const {{x,y}}=getPos(e);ctx.beginPath();ctx.moveTo(x,y);}},{{passive:false}});
canvas.addEventListener('touchmove', e=>{{e.preventDefault();if(!drawing)return;hasDrawn=true;document.getElementById('sig-hint').classList.add('hidden');const {{x,y}}=getPos(e);ctx.lineTo(x,y);ctx.stroke();}},{{passive:false}});
canvas.addEventListener('touchend', ()=>drawing=false);
function clearSig() {{ ctx.clearRect(0,0,canvas.width,canvas.height); hasDrawn=false; document.getElementById('sig-hint').classList.remove('hidden'); }}
async function soumettre() {{
  if (!hasDrawn) {{ document.getElementById('msg').style.display='block'; document.getElementById('msg').textContent='Veuillez signer avant de valider.'; return; }}
  const btn = document.getElementById('btn-submit');
  btn.disabled=true; btn.textContent='Enregistrement...';
  const signature = canvas.toDataURL('image/png');
  try {{
    const resp = await fetch('/soumettre-signature/'+SESSION_ID, {{
      method: 'POST', headers: {{'Content-Type':'application/json'}},
      body: JSON.stringify({{signature_formateur: signature}})
    }});
    const result = await resp.json();
    if (result.success) {{
      document.getElementById('main-card').style.display='none';
      document.getElementById('success').style.display='block';
    }} else {{
      document.getElementById('msg').style.display='block';
      document.getElementById('msg').textContent='Erreur : '+(result.error||'inconnue');
      btn.disabled=false; btn.textContent='✅ Valider et générer le PDF';
    }}
  }} catch(e) {{
    document.getElementById('msg').style.display='block';
    document.getElementById('msg').textContent='Erreur réseau. Réessayez.';
    btn.disabled=false; btn.textContent='✅ Valider et générer le PDF';
  }}
}}
</script>
</body>
</html>"""

@app.route('/soumettre-signature/<session_id>', methods=['POST'])
def soumettre_signature(session_id):
    session = load_session(session_id)
    if not session:
        return jsonify({'success': False, 'error': 'Session introuvable'}), 404
    sig_formateur = request.json.get('signature_formateur')
    session['signature_formateur'] = sig_formateur
    session['signe_le'] = time.time()
    save_session(session_id, session)
    return jsonify({'success': True})

@app.route('/statut/<session_id>', methods=['GET'])
def statut(session_id):
    session = load_session(session_id)
    if not session:
        return jsonify({'signe': False, 'error': 'Session introuvable'})
    signe = session.get('signature_formateur') is not None
    return jsonify({'signe': signe, 'session_id': session_id})

@app.route('/telecharger-pdf-final/<session_id>', methods=['GET'])
def telecharger_pdf_final(session_id):
    session = load_session(session_id)
    if not session:
        return jsonify({'error': 'Session introuvable'}), 404
    sig_formateur = session.get('signature_formateur')
    if not sig_formateur:
        return jsonify({'error': 'Formateur pas encore signé'}), 400
    try:
        pdf_buffer = generer_pdf(session['data'], sig_formateur, session_id)
        return send_file(
            pdf_buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'Emargement_Prevamceo_{session_id}.pdf'
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
