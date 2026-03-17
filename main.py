import os
import io
from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.responses import Response, HTMLResponse
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
import google.generativeai as genai
from fpdf import FPDF
from fpdf.enums import XPos, YPos
from typing import List
from fastapi.middleware.cors import CORSMiddleware

# 1. Load API Key dari .env
load_dotenv()
GEMINI_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_KEY:
    print("ERROR: GEMINI_API_KEY tidak ditemukan di file .env!")

# 2. Konfigurasi Gemini
genai.configure(api_key=GEMINI_KEY)
# Menggunakan Gemini 2.5 Flash (Mendukung Gambar & Teks)
model = genai.GenerativeModel('models/gemini-2.5-flash') 

app = FastAPI(title="AI Papan Tulis ke PDF")

templates = Jinja2Templates(directory="templates")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def process_image_with_gemini(image_bytes: bytes, mime_type: str) -> str:
    """Fungsi Multimodal: Membaca gambar dan merapikan teks sekaligus"""
    try:
        # Menyiapkan payload gambar untuk Gemini
        image_part = {
            "mime_type": mime_type,
            "data": image_bytes
        }
        
        prompt = """
        Tolong analisis foto papan tulis ini. 
        1. Ekstrak semua tulisan yang ada.
        2. Rapikan menjadi materi catatan yang terstruktur (gunakan judul, sub-judul, dan poin-poin).
        3. Perbaiki typo atau kalimat yang tidak lengkap agar mudah dipelajari.
        4. Jika ada rumus, tuliskan dengan jelas.
        Jangan berikan pengantar, langsung berikan isi materinya saja.
        """
        
        response = model.generate_content([prompt, image_part])
        return response.text
    except Exception as e:
        raise Exception(f"Gemini AI Error: {str(e)}")

def create_pdf(text: str) -> bytearray:
    """Mengonversi hasil AI menjadi file PDF"""
    try:
        pdf = FPDF()
        pdf.add_page()
        
        # Menggunakan font Helvetica (Standar)
        pdf.set_font("helvetica", size=12)
        
        # Judul Dokumen - Pakai cara baru sesuai peringatan error
        pdf.set_font("helvetica", style="B", size=16)
        pdf.cell(0, 10, "Catatan Materi Terstruktur", 
                 new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
        pdf.ln(10)
        
        # Isi Materi
        pdf.set_font("helvetica", size=11)
        
        # Bersihkan karakter agar tidak crash (FPDF standar hanya dukung Latin-1)
        # Kita lakukan encode/decode di string-nya, BUKAN di hasil output pdf
        clean_text = text.encode('latin-1', 'replace').decode('latin-1')
        
        # Tulis teks
        pdf.multi_cell(0, 7, clean_text)
        
        # Di fpdf2 terbaru, output() langsung menghasilkan bytearray
        return pdf.output()
    except Exception as e:
        raise Exception(f"PDF Error: {str(e)}")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/upload-note/")
async def upload_and_convert(files: List[UploadFile] = File(...)):
    combined_text = ""
    
    try:
        for index, file in enumerate(files):
            if not file.content_type.startswith('image/'):
                continue # Lewati jika bukan gambar
            
            image_content = await file.read()
            
            print(f"Memproses gambar ke-{index + 1}...")
            prompt_tambahan = f"\n\n--- Bagian {index + 1} ---\n"
            text_result = process_image_with_gemini(image_content, file.content_type)
            
            combined_text += prompt_tambahan + text_result

        print("Generating PDF Gabungan...")
        pdf_bytes = create_pdf(combined_text)

        return Response(
            content=bytes(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": "attachment; filename=Catatan_Lengkap.pdf"
            }
        )
        
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)