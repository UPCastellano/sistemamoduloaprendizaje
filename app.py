from flask import Flask, render_template, request, redirect, jsonify
from flask_sqlalchemy import SQLAlchemy
import requests
import os
from dotenv import load_dotenv
import pickle
import logging
import wikipedia  # Agregar esta importación

# Cargar variables de entorno
load_dotenv()

# Configuración de la app
app = Flask(__name__)

# Configuración de la base de datos
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Configuración de API
API_URL = "https://www.healthcare.gov/api/articles.json"

# Configurar Wikipedia en español
wikipedia.set_lang("es")

# Configurar logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Modelos
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)

class Diagnostic(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    symptoms = db.Column(db.Text, nullable=False)
    diagnosis = db.Column(db.Text, nullable=False)

# Ruta principal
@app.route('/')
def index():
    return render_template('index.html')

# Diagnóstico basado en síntomas
@app.route('/diagnose', methods=['POST'])
def diagnose():
    try:
        logger.debug("Iniciando diagnóstico")
        logger.debug(f"Datos del formulario: {request.form}")
        
        name = request.form.get('name')
        email = request.form.get('email')
        symptoms = request.form.get('symptoms', '').lower()

        if not all([name, email, symptoms]):
            logger.error("Faltan datos en el formulario")
            return jsonify({
                "error": "Todos los campos son requeridos"
            }), 400

        logger.debug("Guardando usuario")
        user = User.query.filter_by(email=email).first()
        if not user:
            user = User(name=name, email=email)
            db.session.add(user)
            db.session.commit()

        logger.debug("Buscando información en Wikipedia")
        try:
            # Buscar en Wikipedia
            search_results = wikipedia.search(f"{symptoms} enfermedad síntomas", results=3)
            articles_info = []
            
            for title in search_results:
                try:
                    page = wikipedia.page(title)
                    articles_info.append({
                        'title': page.title,
                        'url': page.url,
                        'summary': page.summary[:200] + '...'  # Primeros 200 caracteres
                    })
                except:
                    continue
            
            if articles_info:
                diagnosis_text = ""
                for article in articles_info:
                    diagnosis_text += f"<h4><a href='{article['url']}' target='_blank'>{article['title']}</a></h4>"
                    diagnosis_text += f"<p>{article['summary']}</p>"
            else:
                diagnosis_text = f"No se encontró información relacionada con: {symptoms}"

        except Exception as wiki_error:
            logger.error(f"Error en Wikipedia: {wiki_error}")
            diagnosis_text = f"No se pudo obtener información para: {symptoms}"

        logger.debug("Guardando diagnóstico")
        diagnostic = Diagnostic(user_id=user.id, symptoms=symptoms, diagnosis=diagnosis_text)
        db.session.add(diagnostic)
        db.session.commit()

        return redirect('/results')
        
    except Exception as e:
        logger.exception("Error en diagnose:")
        return jsonify({
            "error": "Error en el proceso de diagnóstico",
            "details": str(e)
        }), 500

# Mostrar resultados
@app.route('/results')
def results():
    diagnostics = Diagnostic.query.all()
    return render_template('results.html', diagnostics=diagnostics)

@app.route('/test_api')
def test_api():
    try:
        response = requests.get(
            API_URL,
            timeout=10
        )
        return jsonify({
            "status": response.status_code,
            "response": response.json()[:5]  # Mostrar solo los primeros 5 resultados
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    return response

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    # Cambiar esta línea para Vercel
    app.run()
