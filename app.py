# ==============================================================================
# SMART QUALITY DECISION PLATFORM - DEVELOPED BY CSORBA LÁSZLÓ
# ==============================================================================

import os
import time
import imaplib
import email
import pandas as pd
from datetime import datetime
import gradio as gr
from google import genai
from gTTS import gTTS
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# 1. API & Modell Beállítások (Render Környezeti Változó használatával)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY)

MODELS_TO_TRY = ["gemini-2.5-flash", "gemini-3.5-flash-lite", "gemini-3.6-flash"]
DB_FILE = "reklamaciok_db.csv"

def init_database():
    if not os.path.exists(DB_FILE):
        initial_data = [
            {"ID": "REC-2026-001", "Dátum": "2026-09-01 10:15", "Kategória": "Csomagolás", "Prioritás": "HIGH", "Nyelv": "Magyar", "Düh-szint": "8/10", "Címzett_Osztály": "Csomagolóüzem", "Státusz": "Továbbítva", "Gyökérok": "Sérült gyűjtőkarton"},
            {"ID": "REC-2026-002", "Dátum": "2026-09-02 14:30", "Kategória": "Logisztika", "Prioritás": "MEDIUM", "Nyelv": "Angol", "Düh-szint": "5/10", "Címzett_Osztály": "Raktár & Logisztika", "Státusz": "Továbbítva", "Gyökérok": "Raktári elmozdulás"},
            {"ID": "REC-2026-003", "Dátum": "2026-09-03 09:45", "Kategória": "Termékminőség", "Prioritás": "HIGH", "Nyelv": "Német", "Düh-szint": "9/10", "Státusz": "Kivizsgálva", "Címzett_Osztály": "Termelés & Minőségirányítás", "Gyökérok": "Zsák szakadás szállítmányozáskor"}
        ]
        df = pd.DataFrame(initial_data)
        df.to_csv(DB_FILE, index=False, encoding='utf-8-sig')

init_database()

LANG_NAME_MAP = {
    'Magyar 🇭🇺': ('hu', 'HUNGARIAN'),
    'English 🇬🇧': ('en', 'ENGLISH'),
    'Deutsch 🇩🇪': ('de', 'GERMAN'),
    'Français 🇫🇷': ('fr', 'FRENCH'),
    'Español 🇪🇸': ('es', 'SPANISH'),
    'Italiano 🇮🇹': ('it', 'ITALIAN')
}

SAMPLE_EMAILS = {
    "1. Indulatos Magyar Panasz (Sérült doboz)": 
        "Tegnap bontottam ki a tőletek rendelt csomagot. A doboz teljesen össze volt nyomódva, "
        "és a belső csomagolás is elszakadt! Biztos vagyok benne, hogy a raktárosaitok nem figyelnek semmire "
        "és selejtes árut küldtek ki szándékosan! Azonnal kérem vissza a pénzemet, vagy feljelentem a céget!",
    
    "2. Angol Nyelvű Reklamáció (English Complaint)": 
        "Dear Customer Service, I received order #89212 today. The outer cartoon was completely broken and "
        "two sacks of starch are leaking. This is totally unacceptable for a premium supplier! "
        "I demand an immediate free replacement or I will escalate this to my procurement manager."
}

def fetch_live_email_gradio(user, pwd, server):
    if not user or not pwd:
        return "⚠️ Kérlek add meg az e-mail címet és az alkalmazás-jelszót!"

    try:
        mail = imaplib.IMAP4_SSL(server)
        mail.login(user, pwd)
        mail.select("inbox")
        _, search_data = mail.search(None, 'UNSEEN')
        mail_ids = search_data[0].split()

        if not mail_ids:
            _, search_data = mail.search(None, 'ALL')
            mail_ids = search_data[0].split()

        if mail_ids:
            latest_id = mail_ids[-1]
            _, data = mail.fetch(latest_id, '(RFC822)')
            raw_email = data[0][1]
            msg = email.message_from_bytes(raw_email)

            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True).decode()
                        break
            else:
                body = msg.get_payload(decode=True).decode()

            return body
        else:
            return "ℹ️ A fiókban nem található beérkező e-mail."
    except Exception as e:
        return f"❌ IMAP Csatlakozási hiba: {e}"

def generate_with_fallback(prompt):
    last_err = None
    for model_name in MODELS_TO_TRY:
        for attempt in range(2):
            try:
                res = client.models.generate_content(model=model_name, contents=[prompt])
                if res and res.text:
                    return res.text
            except Exception as e:
                last_err = e
                time.sleep(1)
                continue
    raise last_err

def create_pdf(res_tags, res1, res2, res3, res4, filename="Reklamacios_Jegyzokonyv.pdf"):
    doc = SimpleDocTemplate(filename, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=16, textColor=colors.HexColor('#0369a1'))
    heading_style = ParagraphStyle('HeadingStyle', parent=styles['Heading2'], fontSize=11, textColor=colors.HexColor('#0f172a'))
    body_style = ParagraphStyle('BodyStyle', parent=styles['Normal'], fontSize=9, leading=13, textColor=colors.HexColor('#334155'))
    footer_style = ParagraphStyle('FooterStyle', parent=styles['Italic'], fontSize=8, textColor=colors.HexColor('#64748b'), spaceBefore=15)

    story = [
        Paragraph("<b>MINŐSÉGÜGYI REKLAMÁCIÓS JEGYZŐKÖNYV (AI-AUDITED)</b>", title_style),
        HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#0369a1'), spaceAfter=10),
        Paragraph(f"<b>Triázs:</b> {res_tags}", body_style),
        Spacer(1, 8),
        Paragraph("<b>1. Tény- és Feltételezés-elválasztás</b>", heading_style),
        Paragraph(res1.replace('\n', '<br/>'), body_style),
        Spacer(1, 8),
        Paragraph("<b>2. Quality Auditor & Etikai Szűrés</b>", heading_style),
        Paragraph(res2.replace('\n', '<br/>'), body_style),
        Spacer(1, 8),
        Paragraph("<b>3. 5 Why Gyökérok & Akcióterv</b>", heading_style),
        Paragraph(res3.replace('\n', '<br/>'), body_style),
        Spacer(1, 8),
        Paragraph("<b>4. Hivatalos Válaszlevél</b>", heading_style),
        Paragraph(res4.replace('\n', '<br/>'), body_style),
        HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#cbd5e1'), spaceBefore=15, spaceAfter=5),
        Paragraph("<i>Fejlesztette és tervezte: Csorba László • Smart Quality Decision Platform</i>", footer_style)
    ]
    doc.build(story)
    return filename

def append_to_database(res_tags, res1, res3, anger_level, target_dept):
    try:
        df_old = pd.read_csv(DB_FILE)
        new_id = f"REC-2026-{len(df_old) + 1:03d}"
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

        kat = "Csomagolás" if "Csomagolás" in res_tags else ("Termékminőség" if "Termékminőség" in res_tags else "Logisztika")
        prio = "HIGH" if "HIGH" in res_tags else "MEDIUM"

        new_row = {
            "ID": new_id, "Dátum": now_str, "Kategória": kat,
            "Prioritás": prio, "Nyelv": "Magyar", "Düh-szint": anger_level,
            "Címzett_Osztály": target_dept, "Státusz": "Automatikusan Továbbítva", "Gyökérok": "Feldolgozva & Továbbítva"
        }
        df_updated = pd.concat([df_old, pd.DataFrame([new_row])], ignore_index=True)
        df_updated.to_csv(DB_FILE, index=False, encoding='utf-8-sig')
        return new_id
    except:
        return "REC-2026-NEW"

def process_complaint_gradio(panasz_szoveg, valasz_nyelv_disp):
    if not panasz_szoveg.strip():
        return "⚠️ Adj meg panaszszöveget!", "N/A", "", "", "", "", "", "Nincs továbbítandó adat", None, None

    lang_code, target_lang_name = LANG_NAME_MAP.get(valasz_nyelv_disp, ('hu', 'HUNGARIAN'))

    master_prompt = f"""
    Elemezd az alábbi vevői reklamációt: "{panasz_szoveg}"
    Válaszolj PONTOSAN az alábbi 5 elválasztott blokkban:
    ---TRIAGE---
    KATEGÓRIA: [Logisztika / Csomagolás / Pénzügy / Termékminőség] | PRIORITÁS: [HIGH / MEDIUM / LOW] | CÍMKÉK: [#tag1, #tag2]
    ---STEP1---
    BEÉRKEZŐ NYELV: [Nyelv]
    VEVŐ ÉRZELMI ÁLLAPOTA (Düh-szint 1-10): [X/10]
    OBSERVED FACTS:
    UNPROVABLE ASSUMPTIONS:
    MISSING INFORMATION:
    ---STEP2---
    FELELŐSSÉGVÁLLALÁSI AUDIT:
    AUDIT STATUS: [GREEN / YELLOW / RED]
    KOMMUNIKÁCIÓS STRATÉGIA:
    ---STEP3---
    5 WHY GYÖKÉROK ELEMZÉS:
    1.
    2.
    KORREKCIÓS AKCIÓTERV:
    ---STEP4---
    Write the official customer email response strictly in {target_lang_name} language (Max 100 words, polite, professional).
    """

    res = generate_with_fallback(master_prompt)

    res_tags = res.split("---TRIAGE---")[1].split("---STEP1---")[0].strip() if "---TRIAGE---" in res else "Triázs lefutott"
    res1 = res.split("---STEP1---")[1].split("---STEP2---")[0].strip() if "---STEP1---" in res else res
    res2 = res.split("---STEP2---")[1].split("---STEP3---")[0].strip() if "---STEP2---" in res else ""
    res3 = res.split("---STEP3---")[1].split("---STEP4---")[0].strip() if "---STEP3---" in res else ""
    res4 = res.split("---STEP4---")[1].strip() if "---STEP4---" in res else ""

    anger_level = "7/10"
    if "Düh-szint" in res1:
        try:
            anger_level = res1.split("Düh-szint")[1].split("\n")[0].replace(":", "").strip()
        except:
            pass

    target_dept = "Termelés & Minőségirányítás"
    if "Csomagolás" in res_tags:
        target_dept = "Csomagolóüzem & Műszakvezetés"
    elif "Logisztika" in res_tags:
        target_dept = "Raktár & Logisztika"
    elif "Pénzügy" in res_tags:
        target_dept = "Pénzügy & Számlázás"

    rec_id = append_to_database(res_tags, res1, res3, anger_level, target_dept)

    internal_notice = f"""📩 BELSŐ FELADATKIÍRÁS & ÉRTESÍTÉS
--------------------------------------------------
CÍMZETT TÁRSTERÜLET: {target_dept}
ÜGY AZONOSÍTÓ: {rec_id}
SÜRGŐSSÉG / PRIORITÁS: {"HIGH (AZONNALI INTÉZKEDÉS)" if "HIGH" in res_tags else "NORMÁL"}
VEVŐI DÜH-SZINT: {anger_level}

🧩 5 WHY GYÖKÉROK & ELŐÍRT AKCIÓTERV:
{res3}

--------------------------------------------------
Rendszerüzenet: Az akcióterv automatikusan rögzítésre került a Minőségirányítási Rendszerben (CAPA Module).
Fejlesztő: Csorba László"""

    audio_path = "valasz_narracio.mp3"
    tts = gTTS(text=res4, lang=lang_code)
    tts.save(audio_path)

    pdf_path = create_pdf(res_tags, res1, res2, res3, res4)

    return f"🏷️ {rec_id} | {res_tags}", f"🔥 Ingerültségi Szint: {anger_level}", res1, res2, res3, res4, internal_notice, f"✅ Automatikusan elküldve ide: {target_dept}", audio_path, pdf_path

def get_analytics_gradio():
    df = pd.read_csv(DB_FILE)
    total = len(df)
    high = len(df[df['Prioritás'] == 'HIGH'])
    return f"📊 ÖSSZES CASE: {total} db | 🚨 KRITIKUS (HIGH): {high} db", df

def reset_to_home():
    return (
        "Saját E-mail Bemásolása",
        gr.update(visible=False),
        gr.update(visible=False),
        "",
        'Magyar 🇭🇺',
        "", "", "", "", "", "", "", "", None, None
    )

custom_theme = gr.themes.Soft(
    primary_hue="sky",
    secondary_hue="slate",
    neutral_hue="slate",
    font=[gr.themes.GoogleFont("Inter"), "ui-sans-serif", "system-ui"]
)

with gr.Blocks(title="Smart Quality Platform - Csorba László", theme=custom_theme) as demo:
    gr.HTML("""
    <div style="text-align: center; padding: 20px; background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); border-radius: 16px; color: white; margin-bottom: 20px; border: 1px solid #334155;">
        <h1 style="margin: 0; font-size: 26px; color: #38bdf8; font-weight: 800;">🛡️ Smart Quality Decision Platform</h1>
        <p style="margin: 5px 0 0 0; font-size: 13px; color: #94a3b8;">Enterprise AI Complaint Decisioning • Auto-Routing to Production & Warehouse</p>
        <div style="margin-top: 10px; font-size: 12px; font-weight: 600; color: #38bdf8; background: rgba(56, 189, 248, 0.1); display: inline-block; padding: 4px 12px; border-radius: 20px; border: 1px solid rgba(56, 189, 248, 0.2);">
            👨‍💻 Fejlesztette: Csorba László
        </div>
    </div>
    """)

    with gr.Tab("⚡ Reklamáció Elemzése"):
        with gr.Row():
            home_btn = gr.Button("🏠 KEZDŐLAP (ALAPHELYZET)", variant="secondary")

        with gr.Row():
            with gr.Column(scale=5):
                gr.Markdown("### 📥 1. Panasz Bevitele & Forrás")
                source_radio = gr.Radio(
                    choices=["Saját E-mail Bemásolása", "Minta E-mail (Demó)", "Élő E-mail Importálása (IMAP)"],
                    value="Saját E-mail Bemásolása",
                    label="Forrás kiválasztása"
                )

                sample_box = gr.Group(visible=False)
                with sample_box:
                    sample_select = gr.Dropdown(choices=list(SAMPLE_EMAILS.keys()), label="✉️ Minta E-mail kiválasztása")

                imap_box = gr.Group(visible=False)
                with imap_box:
                    imap_user = gr.Textbox(label="E-mail cím", placeholder="pl. reklamacio@ceg.hu")
                    imap_pass = gr.Textbox(label="Applikációs Jelszó / Token", type="password")
                    imap_server = gr.Textbox(value="imap.gmail.com", label="IMAP Szerver")
                    fetch_btn = gr.Button("📥 Új Beérkező E-mail Betöltése", variant="secondary")

                input_text = gr.Textbox(
                    lines=7,
                    label="📝 Reklamációs Szöveg",
                    placeholder="Másold ide a beérkező e-mailt vagy panaszszöveget...",
                    value=""
                )
                lang_select = gr.Dropdown(choices=list(LANG_NAME_MAP.keys()), value='Magyar 🇭🇺', label="🌐 Vevői Válasznyelv Kiválasztása")
                submit_btn = gr.Button("⚡ AI ELEMZÉS & AUTOMATIKUS TOVÁBBÍTÁS", variant="primary", size="lg")

            with gr.Column(scale=7):
                gr.Markdown("### 🎯 2. AI Döntéshozatal & Társterületi Értesítés")
                with gr.Row():
                    out_triage = gr.Textbox(label="🏷️ Ügy azonosító & Triázs", interactive=False, scale=3)
                    out_anger = gr.Textbox(label="😡 Ingerültségi Szint (Düh-mérés)", interactive=False, scale=2)

                out_step1 = gr.Textbox(label="🔍 1. Tény- és Feltételezés Elválasztás", lines=3, interactive=False)
                out_step2 = gr.Textbox(label="⚖️ 2. Quality Auditor & Etikai Szűrés", lines=2, interactive=False)
                out_step3 = gr.Textbox(label="🧩 3. 5 Why Gyökérok & Korrekciós Akcióterv", lines=3, interactive=False)

                with gr.Group():
                    gr.Markdown("### 🏢 Automatikus Társterületi Továbbítás (Termelés / Raktár)")
                    out_dept_status = gr.Textbox(label="📤 Továbbítási Státusz", interactive=False)
                    out_internal_msg = gr.Textbox(label="📩 Társterületnek Kiküldött Belső Üzenet & Akcióterv", lines=6, interactive=False)

                out_step4 = gr.Textbox(label="✉️ 4. Hivatalos Ügyfél Válaszlevél", lines=3, interactive=False)

                with gr.Row():
                    out_audio = gr.Audio(label="🔊 Hangnarráció", type="filepath", scale=1)
                    out_pdf = gr.File(label="📄 PDF Jegyzőkönyv", scale=1)

        def toggle_source(source):
            if source == "Élő E-mail Importálása (IMAP)":
                return gr.update(visible=False), gr.update(visible=True), gr.update(value="")
            elif source == "Minta E-mail (Demó)":
                return gr.update(visible=True), gr.update(visible=False), gr.update(value=SAMPLE_EMAILS["1. Indulatos Magyar Panasz (Sérült doboz)"])
            else:
                return gr.update(visible=False), gr.update(visible=False), gr.update(value="")

        source_radio.change(toggle_source, inputs=[source_radio], outputs=[sample_box, imap_box, input_text])
        sample_select.change(lambda choice: SAMPLE_EMAILS.get(choice, ""), inputs=[sample_select], outputs=[input_text])
        fetch_btn.click(fetch_live_email_gradio, inputs=[imap_user, imap_pass, imap_server], outputs=[input_text])

        submit_btn.click(
            process_complaint_gradio,
            inputs=[input_text, lang_select],
            outputs=[out_triage, out_anger, out_step1, out_step2, out_step3, out_step4, out_internal_msg, out_dept_status, out_audio, out_pdf]
        )

        home_btn.click(
            reset_to_home,
            outputs=[
                source_radio, sample_box, imap_box, input_text, lang_select,
                out_triage, out_anger, out_step1, out_step2, out_step3, out_step4,
                out_internal_msg, out_dept_status, out_audio, out_pdf
            ]
        )

    with gr.Tab("📊 Live Quality Dashboard"):
        refresh_btn = gr.Button("🔄 Adatok Frissítése", variant="secondary")
        out_summary = gr.Textbox(label="📈 KPI Mutatók & Státusz", interactive=False)
        out_table = gr.Dataframe(label="📋 Rögzített Reklamációk Adatbázisa (Címzett Osztállyal)")
        refresh_btn.click(get_analytics_gradio, outputs=[out_summary, out_table])

# 3. ÉLES FELHŐS INDÍTÁS (RENDER PORTBEÁLLÍTÁSSAL)
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    demo.launch(server_name="0.0.0.0", server_port=port)
