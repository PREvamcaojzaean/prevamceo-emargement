from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from PIL import Image
import base64, io, os, json, uuid, time

app = Flask(__name__)
CORS(app)

W, H = A4

LOGO_B64 = "iVBORw0KGgoAAAANSUhEUgAAARgAAACMCAIAAAAobCE6AAABsUlEQVR4nO3BMQEAAADCoPVP7WsIoAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAeAMBuAABHgAAAABJRU5ErkJggg=="

# Stockage temporaire des sessions (en production utiliser Redis)
sessions = {}

def b64_to_image(b64_str):
    if ',' in b64_str:
        b64_str = b64_str.split(',')[1]
    img_data = base64.b64decode(b64_str)
    return Image.open(io.BytesIO(img_data)).convert('RGBA')

def generer_pdf(data, sig_formateur=None):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    
    mL, mR, mT = 15*mm, 15*mm, 12*mm
    cW = W - mL - mR

    # ===== HEADER =====
    # Logo
    try:
        logo_data = base64.b64decode(LOGO_B64)
        logo_img = Image.open(io.BytesIO(logo_data))
        logo_buffer = io.BytesIO()
        logo_img.save(logo_buffer, format='PNG')
        logo_buffer.seek(0)
        c.drawImage(logo_buffer, mL, H - mT - 25*mm, width=45*mm, height=20*mm, preserveAspectRatio=True, mask='auto')
    except:
        pass

    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(W/2, H - mT - 12*mm, "Feuille de présence")
    c.setFont("Helvetica", 8)
    c.drawRightString(W - mR, H - mT - 6*mm, "Enregistrement EQ003")
    c.drawRightString(W - mR, H - mT - 10*mm, "Version 2 16/2/26")
    c.setLineWidth(0.5)
    c.rect(mL, H - mT - 28*mm, cW, 28*mm, stroke=1, fill=0)

    # ===== TABLE INFOS =====
    y = H - mT - 28*mm - 16*mm
    col4 = cW / 4
    headers1 = ['Client', 'Titre de la formation', 'Session n°', 'Dates de formation']
    vals1 = [data.get('entreprise',''), data.get('titre',''), data.get('session',''), data.get('date','')]
    
    for i in range(4):
        c.setFillColorRGB(0.9, 0.9, 0.9)
        c.rect(mL + i*col4, y + 8*mm, col4, 7*mm, stroke=1, fill=1)
        c.setFillColorRGB(0,0,0)
        c.setFont("Helvetica-Bold", 8)
        c.drawCentredString(mL + i*col4 + col4/2, y + 11*mm, headers1[i])
        c.setFillColorRGB(1,1,1)
        c.rect(mL + i*col4, y, col4, 8*mm, stroke=1, fill=1)
        c.setFillColorRGB(0,0,0)
        c.setFont("Helvetica", 8)
        t = vals1[i][:22] if len(vals1[i]) > 22 else vals1[i]
        c.drawCentredString(mL + i*col4 + col4/2, y + 3*mm, t)

    # Ligne 2
    y -= 18*mm
    col3 = [cW*0.35, cW*0.30, cW*0.35]
    headers2 = ['Adresse de la formation', 'Horaires', 'Type de formation']
    vals2 = [data.get('adresse',''), data.get('horaires',''), data.get('type_formation','Présentiel synchrone')]
    x = mL
    for i in range(3):
        c.setFillColorRGB(0.9,0.9,0.9)
        c.rect(x, y+8*mm, col3[i], 7*mm, stroke=1, fill=1)
        c.setFillColorRGB(0,0,0)
        c.setFont("Helvetica-Bold", 8)
        c.drawCentredString(x+col3[i]/2, y+11*mm, headers2[i])
        c.setFillColorRGB(1,1,1)
        c.rect(x, y, col3[i], 8*mm, stroke=1, fill=1)
        c.setFillColorRGB(0,0,0)
        c.setFont("Helvetica", 8)
        if i == 0:
            parts = vals2[i].split(',')
            c.drawCentredString(x+col3[i]/2, y+5*mm, parts[0])
            if len(parts) > 1:
                c.drawCentredString(x+col3[i]/2, y+2*mm, parts[1].strip())
        else:
            c.drawCentredString(x+col3[i]/2, y+3.5*mm, vals2[i])
        x += col3[i]

    # ===== TABLEAU EMARGEMENT =====
    y -= 8*mm
    colN = cW * 0.28
    colS = cW * 0.36
    rowH = 12*mm

    # Header
    c.setFillColorRGB(0.92,0.92,0.92)
    c.rect(mL, y, colN, 18*mm, stroke=1, fill=1)
    c.rect(mL+colN, y, colS*2, 18*mm, stroke=1, fill=1)
    c.setFillColorRGB(0,0,0)
    c.setFont("Helvetica-Bold", 8)
    c.drawCentredString(mL+colN/2, y+13*mm, "Émargement des apprenants")
    c.setFont("Helvetica", 7)
    c.drawCentredString(mL+colN/2, y+10*mm, "Nom et Prénom")
    c.drawCentredString(mL+colN/2, y+7*mm, "(Par cette signature j'atteste")
    c.drawCentredString(mL+colN/2, y+4.5*mm, "avoir reçu la formation ci-dessus)")
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(mL+colN+colS, y+13*mm, data.get('date',''))
    c.drawCentredString(mL+colN+colS/2, y+8*mm, "Matin")
    c.setFont("Helvetica", 7)
    c.drawCentredString(mL+colN+colS+colS/2, y+13*mm, "Après-midi")
    c.drawCentredString(mL+colN+colS+colS/2, y+9.5*mm, "(Par cette signature j'atteste")
    c.drawCentredString(mL+colN+colS+colS/2, y+7*mm, "avoir reçu la formation ci-dessus)")
    c.line(mL+colN+colS, y, mL+colN+colS, y+18*mm)

    # Participants
    y -= rowH
    participants = data.get('participants', [])
    for i, p in enumerate(participants):
        fill = 0.97 if i%2==0 else 1.0
        c.setFillColorRGB(fill,fill,fill)
        c.rect(mL, y, colN, rowH, stroke=1, fill=1)
        c.setFillColorRGB(1,1,1)
        c.rect(mL+colN, y, colS, rowH, stroke=1, fill=1)
        c.rect(mL+colN+colS, y, colS, rowH, stroke=1, fill=1)
        
        c.setFillColorRGB(0,0,0)
        c.setFont("Helvetica", 9)
        nom_complet = f"{p.get('prenom','')} {p.get('nom','')}".strip()
        c.drawString(mL+2*mm, y+4.5*mm, nom_complet)

        # Signature du stagiaire
        sig_b64 = p.get('signature','')
        if sig_b64:
            try:
                sig_img = b64_to_image(sig_b64)
                sig_buffer = io.BytesIO()
                sig_img.save(sig_buffer, format='PNG')
                sig_buffer.seek(0)
                c.drawImage(sig_buffer, mL+colN+2*mm, y+1*mm, 
                           width=colS-4*mm, height=rowH-2*mm, 
                           preserveAspectRatio=True, mask='auto')
            except:
                c.setFont("Helvetica", 8)
                c.setFillColorRGB(0.1,0.42,0.29)
                heure = p.get('heure','')
                c.drawCentredString(mL+colN+colS/2, y+4.5*mm, f"✓ Signé {heure}")
                c.setFillColorRGB(0,0,0)
        
        y -= rowH

    # Formateur
    c.setFillColorRGB(0.92,0.92,0.92)
    c.rect(mL, y, colN, 18*mm, stroke=1, fill=1)
    c.setFillColorRGB(1,1,1)
    c.rect(mL+colN, y, colS, 18*mm, stroke=1, fill=1)
    c.rect(mL+colN+colS, y, colS, 18*mm, stroke=1, fill=1)
    c.setFillColorRGB(0,0,0)
    c.setFont("Helvetica-Bold", 8)
    c.drawCentredString(mL+colN/2, y+13*mm, "Formateur")
    c.setFont("Helvetica", 9)
    c.drawCentredString(mL+colN/2, y+9*mm, data.get('formateur',''))
    c.setFont("Helvetica", 7)
    c.drawCentredString(mL+colN/2, y+6*mm, "(Par cette signature j'atteste")
    c.drawCentredString(mL+colN/2, y+3.5*mm, "avoir animé la formation ci-dessus)")

    # Signature formateur
    if sig_formateur:
        try:
            sig_img = b64_to_image(sig_formateur)
            sig_buffer = io.BytesIO()
            sig_img.save(sig_buffer, format='PNG')
            sig_buffer.seek(0)
            c.drawImage(sig_buffer, mL+colN+2*mm, y+1*mm,
                       width=colS-4*mm, height=16*mm,
                       preserveAspectRatio=True, mask='auto')
        except:
            pass

    # Footer
    c.setFont("Helvetica", 6)
    c.setFillColorRGB(0.3,0.3,0.3)
    fY = 20*mm
    c.drawCentredString(W/2, fY, "Les informations recueillies sont enregistrées dans un fichier informatisé par PREVAMCEO pour traiter votre inscription en formation continue.")
    c.drawCentredString(W/2, fY-3.5*mm, "Conformément à la loi « informatique et libertés » vous pouvez exercer votre droit d'accès en contactant jparnaud@prevamceo.fr")
    c.drawCentredString(W/2, fY-7*mm, "Prévamcéo - 11 B allée de la Falaise - 13820 Ensuès-la-Redonne – 06 08 13 92 57 – contact@prevamceo.fr – Siret 939 109 252 00014")

    c.save()
    buffer.seek(0)
    return buffer

# ===== ROUTES =====

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'service': 'Prevamceo Emargement'})

@app.route('/creer-session', methods=['POST'])
def creer_session():
    """
    Make.com envoie les données ici.
    Crée une session et retourne un lien de signature pour le formateur.
    """
    data = request.json
    session_id = str(uuid.uuid4())[:8]
    sessions[session_id] = {
        'data': data,
        'signature_formateur': None,
        'cree_le': time.time()
    }
    
    base_url = request.host_url.rstrip('/')
    lien_signature = f"{base_url}/signer/{session_id}"
    
    return jsonify({
        'session_id': session_id,
        'lien_signature': lien_signature,
        'message': 'Session créée — envoyez ce lien au formateur'
    })

@app.route('/signer/<session_id>', methods=['GET'])
def page_signature(session_id):
    """Page de signature pour le formateur."""
    if session_id not in sessions:
        return "Session expirée ou introuvable.", 404
    
    session = sessions[session_id]
    data = session['data']
    formateur = data.get('formateur', 'Formateur')
    formation = data.get('titre', 'Formation')
    date = data.get('date', '')
    participants = data.get('participants', [])
    
    liste_html = ''.join([
        f"<div class='participant'>✅ {p.get('prenom','')} {p.get('nom','')}</div>"
        for p in participants
    ])
    
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
.card {{ margin: 16px; background: white; border-radius: 12px; padding: 20px; }}
.card h2 {{ font-size: 14px; font-weight: 600; color: #1a3a5c; margin-bottom: 12px; }}
.info {{ font-size: 13px; color: #555; margin-bottom: 6px; }}
.participant {{ font-size: 13px; color: #1a6b4a; padding: 4px 0; border-bottom: 1px solid #f0f0f0; }}
.sig-zone label {{ display: block; font-size: 12px; font-weight: 600; color: #666; text-transform: uppercase; letter-spacing: 0.4px; margin-bottom: 8px; }}
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
.msg {{ padding: 12px; border-radius: 8px; font-size: 13px; display: none; margin-bottom: 12px; }}
.msg.error {{ background: #fff0f0; color: #a32d2d; display: block; }}
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
  <h2>Participants ({len(participants)})</h2>
  {liste_html}
  <br>
  <div class="sig-zone">
    <label>Votre signature <span style="color:#e24b4a;">*</span></label>
    <div class="sig-wrap">
      <canvas id="sig-canvas"></canvas>
      <div class="sig-hint" id="sig-hint">✍️ Signez ici avec le doigt</div>
    </div>
    <div style="display:flex;justify-content:flex-end;margin-top:4px;">
      <button class="btn-clear" onclick="clearSig()">Effacer</button>
    </div>
  </div>
  <div class="msg" id="msg"></div>
  <button class="btn-submit" id="btn-submit" onclick="soumettre()">✅ Valider et générer le PDF</button>
</div>

<div class="success" id="success">
  <div class="icon">✅</div>
  <h2>PDF généré !</h2>
  <p style="font-size:14px;color:#555;margin-top:8px;">La feuille de présence a été envoyée par email.<br><br>
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
canvas.addEventListener('touchstart', e=>{{e.preventDefault();drawing=true;const {{x,y}}=getPos(e);ctx.beginPath();ctx.moveTo(x,y);}},{{passive:false}});
canvas.addEventListener('touchmove', e=>{{e.preventDefault();if(!drawing)return;hasDrawn=true;document.getElementById('sig-hint').classList.add('hidden');const {{x,y}}=getPos(e);ctx.lineTo(x,y);ctx.stroke();}},{{passive:false}});
canvas.addEventListener('touchend', ()=>drawing=false);

function clearSig() {{ ctx.clearRect(0,0,canvas.width,canvas.height); hasDrawn=false; document.getElementById('sig-hint').classList.remove('hidden'); }}

async function soumettre() {{
  if (!hasDrawn) {{ document.getElementById('msg').textContent='Veuillez signer avant de valider.'; document.getElementById('msg').className='msg error'; return; }}
  const btn = document.getElementById('btn-submit');
  btn.disabled=true; btn.textContent='Génération en cours...';
  const signature = canvas.toDataURL('image/png');
  try {{
    const resp = await fetch('/soumettre-signature/'+SESSION_ID, {{
      method: 'POST',
      headers: {{'Content-Type':'application/json'}},
      body: JSON.stringify({{signature_formateur: signature}})
    }});
    const result = await resp.json();
    if (result.success) {{
      document.getElementById('main-card').style.display='none';
      document.getElementById('success').style.display='block';
    }} else {{
      document.getElementById('msg').textContent='Erreur : '+result.error;
      document.getElementById('msg').className='msg error';
      btn.disabled=false; btn.textContent='✅ Valider et générer le PDF';
    }}
  }} catch(e) {{
    document.getElementById('msg').textContent='Erreur réseau. Réessayez.';
    document.getElementById('msg').className='msg error';
    btn.disabled=false; btn.textContent='✅ Valider et générer le PDF';
  }}
}}
</script>
</body>
</html>"""

@app.route('/soumettre-signature/<session_id>', methods=['POST'])
def soumettre_signature(session_id):
    """Le formateur soumet sa signature — génère le PDF et l'envoie."""
    if session_id not in sessions:
        return jsonify({'success': False, 'error': 'Session introuvable'}), 404
    
    session_data = sessions[session_id]
    sig_formateur = request.json.get('signature_formateur')
    
    # Générer le PDF
    try:
        pdf_buffer = generer_pdf(session_data['data'], sig_formateur)
        
        # Stocker le PDF dans la session
        sessions[session_id]['pdf'] = pdf_buffer.getvalue()
        sessions[session_id]['signature_formateur'] = sig_formateur
        
        return jsonify({'success': True, 'message': 'PDF généré'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/telecharger-pdf/<session_id>', methods=['GET'])
def telecharger_pdf(session_id):
    """Make.com télécharge le PDF généré."""
    if session_id not in sessions or 'pdf' not in sessions[session_id]:
        return jsonify({'error': 'PDF non disponible'}), 404
    
    pdf_data = sessions[session_id]['pdf']
    return send_file(
        io.BytesIO(pdf_data),
        mimetype='application/pdf',
        as_attachment=True,
        download_name='Feuille_Presence_Prevamceo.pdf'
    )

@app.route('/statut/<session_id>', methods=['GET'])
def statut(session_id):
    """Make.com vérifie si le formateur a signé."""
    if session_id not in sessions:
        return jsonify({'signe': False, 'error': 'Session introuvable'})
    
    session_data = sessions[session_id]
    signe = 'pdf' in session_data
    
    return jsonify({
        'signe': signe,
        'session_id': session_id
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
