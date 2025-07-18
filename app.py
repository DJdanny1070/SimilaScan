from flask import Flask, render_template, request, send_file
import os
import difflib
from werkzeug.utils import secure_filename
import io
import pandas as pd
from fpdf import FPDF
import nltk
from nltk.corpus import wordnet

# === Auto-download NLTK data if missing ===
try:
    wordnet.synsets('test')
except LookupError:
    nltk.download('wordnet')
    nltk.download('stopwords')
    nltk.download('omw-1.4')

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

latest_results = []

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/compare', methods=['POST'])
def compare():
    global latest_results
    for f in os.listdir(app.config['UPLOAD_FOLDER']):
        os.remove(os.path.join(app.config['UPLOAD_FOLDER'], f))

    original_file = request.files['original']
    original_filename = secure_filename(original_file.filename)
    original_path = os.path.join(app.config['UPLOAD_FOLDER'], original_filename)
    original_file.save(original_path)
    original_text = read_file(original_path)

    student_files = request.files.getlist('students')
    if not student_files:
        return "No student files uploaded.", 400

    results = []
    for student_file in student_files:
        filename = secure_filename(student_file.filename)

        # Accept only .txt files
        if not filename.lower().endswith(".txt"):
            print(f"Skipped file: {filename} (Invalid file type)")
            continue

        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        student_file.save(filepath)

        student_text = read_file(filepath)
        similarity = calculate_similarity(original_text, student_text)
        verdict = interpret_similarity(similarity)
        results.append((filename, similarity, verdict))

    latest_results = results
    return render_template('index.html', results=results)

@app.route('/download-report')
def download_report():
    global latest_results
    format = request.args.get('format', 'excel')

    if not latest_results:
        return "No report available to download.", 400

    if format == 'excel':
        df = pd.DataFrame(latest_results, columns=["Student File", "Similarity (%)", "Verdict"])
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name="Similarity Report")
        output.seek(0)

        return send_file(
            output,
            as_attachment=True,
            download_name="similarity_report.xlsx",
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

    elif format == 'pdf':
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=26)
        pdf.cell(200, 10, txt="SIMILARITY REPORT", ln=True, align='C')
        pdf.ln(10)

        pdf.set_font("Arial", "B", size=12)
        pdf.cell(70, 10, txt="Filename", border=1)
        pdf.cell(40, 10, txt="Similarity (%)", border=1)
        pdf.cell(80, 10, txt="Verdict", border=1)
        pdf.ln()

        pdf.set_font("Arial", size=12)
        for filename, similarity, verdict in latest_results:
            pdf.cell(70, 10, txt=filename, border=1)
            pdf.cell(40, 10, txt=str(similarity), border=1)
            pdf.cell(80, 10, txt=verdict, border=1)
            pdf.ln()

        pdf_output = io.BytesIO()
        pdf_bytes = pdf.output(dest='S').encode('latin1')
        pdf_output.write(pdf_bytes)
        pdf_output.seek(0)

        return send_file(
            pdf_output,
            as_attachment=True,
            download_name="similarity_report.pdf",
            mimetype='application/pdf'
        )
    else:
        return "Invalid format requested.", 400

def read_file(path):
    try:
        with open(path, 'r', encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        print(f"Error reading file {path}: {e}")
        return ""

# === Text Preprocessing + Synonym Normalization ===
def synonym_normalize(text):
    words = text.split()
    normalized = []

    for word in words:
        synsets = wordnet.synsets(word)
        if synsets:
            lemma = synsets[0].lemmas()[0].name().replace('_', ' ')
            normalized.append(lemma.lower())
        else:
            normalized.append(word.lower())

    return ' '.join(normalized)

def calculate_similarity(text1, text2):
    text1 = synonym_normalize(text1)
    text2 = synonym_normalize(text2)

    sequence = difflib.SequenceMatcher(None, text1, text2)
    return round(sequence.ratio() * 100, 2)

def interpret_similarity(similarity):
    if similarity >= 80:
        return "Definitely Copied"
    elif similarity >= 50:
        return "Somewhat Copied"
    elif similarity >= 20:
        return "Slightly Similar"
    else:
        return "Unique Content"

if __name__ == '__main__':
    app.run(debug=True)
