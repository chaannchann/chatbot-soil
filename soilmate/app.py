import os
import json
import uuid
from flask import Flask, render_template, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from PIL import Image, ImageOps

import torch
import torch.nn as nn
from torchvision import transforms, models

from config import Config
from db import db_cursor
from chatbot import ChatBot
from planting import plant_now, format_planting_reply, ph_now
from history import (
    log_chat,
    log_scan,
    recent_scans,
    recent_chats,
    get_scan,
    delete_scan,
    delete_user_history,
)
from quality import assess_image, normalised_entropy, message_for, TIPS
from soil_catalog import canonical_name, display_name_for, soil_profile

from flask_login import LoginManager, current_user, login_user, logout_user
from flask_bcrypt import Bcrypt

from users import (
    validate_registration,
    validate_profile,
    find_by_id,
    find_by_login,
    create_user,
    update_profile,
    set_avatar,
)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = Config.UPLOAD_FOLDER
app.config['SECRET_KEY'] = Config.SECRET_KEY
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
)
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

AVATAR_DIR = os.path.join(app.config['UPLOAD_FOLDER'], 'avatars')
AVATAR_SIZE = 256
os.makedirs(AVATAR_DIR, exist_ok=True)

bcrypt = Bcrypt(app)

login_manager = LoginManager()
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    return find_by_id(user_id)


@login_manager.unauthorized_handler
def unauthorized():
    return jsonify({'error': 'Please log in first.'}), 401


def current_user_id():
    """Numeric id of the logged-in user, or None for anonymous visitors."""
    return current_user.numeric_id if current_user.is_authenticated else None

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'bmp'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ----------------- AVATARS -----------------
def avatar_url(filename):
    """Public URL for a stored avatar, or None when the account has none."""
    return f"/avatars/{filename}" if filename else None


def save_avatar(upload):
    """Center-crop the upload to a square, shrink it, and store it as JPEG."""
    image = Image.open(upload.stream)
    image = ImageOps.exif_transpose(image).convert('RGB')

    width, height = image.size
    side = min(width, height)
    left = (width - side) // 2
    top = (height - side) // 2
    image = image.crop((left, top, left + side, top + side))
    image = image.resize((AVATAR_SIZE, AVATAR_SIZE), Image.LANCZOS)

    name = f"{uuid.uuid4().hex}.jpg"
    image.save(os.path.join(AVATAR_DIR, name), 'JPEG', quality=88, optimize=True)
    return name


def remove_avatar_file(filename):
    if not filename:
        return
    try:
        os.remove(os.path.join(AVATAR_DIR, os.path.basename(filename)))
    except OSError:
        pass  # already gone


def soil_details(soil_name):
    """Description, improvement tips and compatible crops for a soil type.

    ``soil_name`` may be a raw model class (``Clay_soil``), a stored scan label
    (``Clay Soil``), or a legacy database name (``soil_with_algae``). The shared
    catalog resolves all of them to the canonical name stored in PostgreSQL.
    """
    month = ph_now().month
    canonical = canonical_name(soil_name) or str(soil_name or '').strip()
    display_name = display_name_for(soil_name)
    catalog = soil_profile(soil_name) or {}

    with db_cursor() as cur:
        cur.execute(
            """
            SELECT id, name, description, improvement_tips
            FROM soil_types
            WHERE name = %s
            LIMIT 1
            """,
            (canonical,),
        )
        soil = cur.fetchone()

        # Fallback for databases that still hold an older spelling of the name.
        if not soil:
            cur.execute("SELECT id, name, description, improvement_tips FROM soil_types")
            soil = next(
                (
                    row for row in cur.fetchall()
                    if canonical_name(row['name']) == canonical
                ),
                None,
            )

        recommendations = []
        if soil:
            cur.execute(
                """
                SELECT
                    c.common_name, c.local_name, c.category,
                    c.germination_days_min, c.germination_days_max,
                    c.harvest_days_min, c.harvest_days_max, c.ideal_planting_season,
                    EXISTS (
                        SELECT 1 FROM crop_planting_months m
                        WHERE m.crop_id = c.id AND m.month = %s
                    ) AS in_season_now
                FROM crops c
                JOIN crop_soil_compatibility csc ON c.id = csc.crop_id
                WHERE csc.soil_type_id = %s
                ORDER BY in_season_now DESC, c.category, c.common_name
                """,
                (month, soil['id']),
            )
            recommendations = [dict(row) for row in cur.fetchall()]

    soil = soil or {}
    return {
        'display_name': display_name,
        'description': soil.get('description') or catalog.get('description', ''),
        'improvement_tips': soil.get('improvement_tips') or catalog.get('improvement_tips', ''),
        'recommendations': recommendations,
    }


# ----------------- LOAD TRAINED AI MODEL -----------------
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
CONFIDENCE_THRESHOLD = Config.CONFIDENCE_THRESHOLD  # e.g., 0.70 or 0.75

# 1. Load Classes from Colab export
with open(Config.CLASSES_PATH, "r") as f:
    CLASS_NAMES = json.load(f)

# 2. Build MobileNetV2 Architecture & Load Weights
model = models.mobilenet_v2(weights=None)
in_features = model.classifier[1].in_features
model.classifier[1] = nn.Linear(in_features, len(CLASS_NAMES))

model.load_state_dict(torch.load(Config.MODEL_PATH, map_location=DEVICE))
model = model.to(DEVICE)
model.eval()
print(f"[OK] AI Model loaded successfully on {DEVICE} with {len(CLASS_NAMES)} classes: {CLASS_NAMES}")

# ----------------- LOAD AGRICULTURAL CHATBOT -----------------
bot = ChatBot()
print(f"[OK] Knowledge base loaded: {len(bot.intents)} intents")

# 3. Image Preprocessing Transform
inference_transforms = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
])

# ----------------- ROUTES -----------------
@app.route('/')
def index():
    return render_template('index.html')


# ----------------- AUTH -----------------
@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''

    error = validate_registration(username, email, password)
    if error:
        return jsonify({'error': error}), 400

    if find_by_login(username) or find_by_login(email):
        return jsonify({'error': 'That username or email is already registered.'}), 409

    password_hash = bcrypt.generate_password_hash(password).decode('utf-8')
    try:
        user = create_user(username, email, password_hash)
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 409

    login_user(user)
    return jsonify({
        'authenticated': True,
        'username': user.username,
        'email': user.email,
        'avatar': avatar_url(user.avatar),
    })


@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json(silent=True) or {}
    identifier = (data.get('username') or '').strip()
    password = data.get('password') or ''

    if not identifier or not password:
        return jsonify({'error': 'Enter your username and password.'}), 400

    row = find_by_login(identifier)
    if not row or not bcrypt.check_password_hash(row['password_hash'], password):
        return jsonify({'error': 'Invalid username or password.'}), 401

    user = find_by_id(row['id'])
    login_user(user)
    return jsonify({
        'authenticated': True,
        'username': user.username,
        'email': user.email,
        'avatar': avatar_url(user.avatar),
    })


@app.route('/api/logout', methods=['POST'])
def logout():
    logout_user()
    return jsonify({'authenticated': False})


@app.route('/api/me')
def me():
    if current_user.is_authenticated:
        return jsonify({
            'authenticated': True,
            'username': current_user.username,
            'email': current_user.email,
            'avatar': avatar_url(current_user.avatar),
        })
    return jsonify({'authenticated': False})


# ----------------- PROFILE -----------------
@app.route('/avatars/<path:filename>')
def avatar_file(filename):
    return send_from_directory(AVATAR_DIR, filename, max_age=3600)


@app.route('/api/profile', methods=['GET', 'POST'])
def profile():
    if not current_user.is_authenticated:
        return jsonify({'error': 'Please log in first.'}), 401

    if request.method == 'GET':
        return jsonify({
            'username': current_user.username,
            'email': current_user.email,
            'avatar': avatar_url(current_user.avatar),
        })

    username = (request.form.get('username') or '').strip()
    email = (request.form.get('email') or '').strip().lower()

    error = validate_profile(username, email)
    if error:
        return jsonify({'error': error}), 400

    upload = request.files.get('avatar')
    remove_avatar = (request.form.get('remove_avatar') or '').lower() in {'1', 'true', 'yes'}

    if upload and upload.filename and not allowed_file(upload.filename):
        return jsonify({'error': 'Avatar must be a PNG, JPG, WEBP, or BMP image.'}), 400
    if upload and upload.filename and request.content_length and request.content_length > 6 * 1024 * 1024:
        return jsonify({'error': 'Avatar image must be smaller than 6 MB.'}), 400

    new_avatar = None
    if upload and upload.filename:
        try:
            new_avatar = save_avatar(upload)
        except Exception:
            return jsonify({'error': 'Could not read that image. Please try another one.'}), 400

    old_avatar = current_user.avatar

    try:
        user = update_profile(current_user.numeric_id, username, email)
    except ValueError as exc:
        remove_avatar_file(new_avatar)
        return jsonify({'error': str(exc)}), 409

    avatar_changed = False
    if new_avatar:
        user = set_avatar(current_user.numeric_id, new_avatar)
        avatar_changed = True
    elif remove_avatar and old_avatar:
        user = set_avatar(current_user.numeric_id, None)
        avatar_changed = True

    if avatar_changed and old_avatar != (user.avatar if user else None):
        remove_avatar_file(old_avatar)

    return jsonify({
        'username': user.username,
        'email': user.email,
        'avatar': avatar_url(user.avatar),
    })


@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json(silent=True) or {}
    message = (data.get('message') or '').strip()
    session_id = data.get('session_id')
    known_soil = data.get('soil_type')

    preferred_language = (data.get('lang') or data.get('language') or '').lower()
    result = bot.respond(
        message,
        session_id=session_id,
        known_soil=known_soil,
        preferred_language=preferred_language or None,
    )

    if result.get('action') == 'plant_now':
        language = result.get('language', 'en')
        try:
            planting_data = plant_now(result.get('soil_type'), language=language)
            result['reply'] = format_planting_reply(planting_data, language=language)
            result['planting'] = planting_data
        except Exception:
            if language == 'tl':
                result['reply'] = (
                    "Hindi ko maabot ang crop calendar ngayon. "
                    "Subukan muli sa ilang sandali, o gamitin ang "
                    "*Ano ang puwedeng itanim ngayong buwan?* na button sa sidebar."
                )
            else:
                result['reply'] = (
                    "I couldn't reach the crop calendar just now. "
                    "Please try again in a moment, or use the "
                    "*What can I plant this month?* button in the sidebar."
                )

    user_id = current_user_id()
    if user_id is not None:
        if message:
            log_chat(session_id, 'user', message, user_id=user_id)
        log_chat(session_id, 'bot', result['reply'],
                 intent=result.get('intent'), confidence=result.get('confidence'),
                 user_id=user_id)

    return jsonify(result)


@app.route('/api/plant-now', methods=['GET', 'POST'])
def plant_now_endpoint():
    """Crops suited to the current month, optionally filtered by soil type."""
    if request.method == 'POST':
        payload = request.get_json(silent=True) or {}
        soil = payload.get('soil_type')
        language = payload.get('lang') or payload.get('language') or 'en'
    else:
        soil = request.args.get('soil')
        language = request.args.get('lang') or request.args.get('language') or 'en'

    try:
        return jsonify(plant_now(soil or None, language=language))
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/predict-soil', methods=['POST'])
def predict_soil():
    if 'image' not in request.files:
        return jsonify({'error': 'No image uploaded'}), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    if not allowed_file(file.filename):
        return jsonify({'error': 'Unsupported file type. Please upload a PNG or JPG image.'}), 400

    user_id = current_user_id()

    safe_name = secure_filename(file.filename)
    stored_name = f"{uuid.uuid4().hex}_{safe_name}"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], stored_name)
    file.save(filepath)

    try:
        image = Image.open(filepath).convert("RGB")

        # 1. Pre-inference quality check (blur, extreme lighting)
        quality = assess_image(image)
        if not quality["ok"]:
            scan_id = (
                log_scan(None, stored_name, None, 0.0, False, user_id=user_id)
                if user_id is not None else None
            )
            return jsonify({
                'identified': False,
                'reason': quality['reason'],
                'scan_id': scan_id,
                'filename': stored_name,
                'confidence': 0.0,
                'message': quality['message'],
                'tips': quality['tips'],
            })

        tensor = inference_transforms(image).unsqueeze(0).to(DEVICE)

        # 2. Run PyTorch Model Inference
        with torch.no_grad():
            outputs = model(tensor)
            probabilities = torch.softmax(outputs, dim=1)[0]
            max_prob, pred_idx = torch.max(probabilities, dim=0)

        confidence = max_prob.item()
        predicted_raw = CLASS_NAMES[pred_idx.item()]
        uncertainty = normalised_entropy(probabilities.tolist())

        # 3. REJECTION / NO-GUESSING LOGIC
        # If confidence is below threshold OR distribution is flat/ambiguous
        if confidence < CONFIDENCE_THRESHOLD or uncertainty > 0.92:
            scan_id = (
                log_scan(None, stored_name, predicted_raw, confidence, False, user_id=user_id)
                if user_id is not None else None
            )
            return jsonify({
                'identified': False,
                'reason': 'low_confidence',
                'scan_id': scan_id,
                'filename': stored_name,
                'confidence': confidence,
                'uncertainty': round(uncertainty, 3),
                'message': "I cannot identify this soil type with certainty. Please upload a clearer close-up of the soil surface.",
                'tips': TIPS,
            })

        # 4. Fetch details from PostgreSQL
        details = soil_details(predicted_raw)
        scan_id = (
            log_scan(None, stored_name, details['display_name'], confidence, True, user_id=user_id)
            if user_id is not None else None
        )

        # Special note if Concrete is detected
        is_concrete = (canonical_name(predicted_raw) == "Concrete Surface")

        return jsonify({
            'identified': True,
            'scan_id': scan_id,
            'filename': stored_name,
            'soil_type': details['display_name'],
            'raw_class': predicted_raw,
            'is_concrete': is_concrete,
            'confidence': confidence,
            **details,
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/history', methods=['GET', 'DELETE'])
def history_endpoint():
    user_id = current_user_id()
    if user_id is None:
        # Guest sessions are intentionally ephemeral: nothing is saved or shown.
        if request.method == 'DELETE':
            return jsonify({'error': 'Please log in to manage saved history.'}), 401
        return jsonify({
            'scans': [],
            'chats': [],
            'requires_login': True,
        })

    if request.method == 'DELETE':
        scan_count, chat_count, filenames = delete_user_history(user_id)

        for filename in filenames:
            # basename() keeps a crafted database value from escaping the folder.
            path = os.path.join(app.config['UPLOAD_FOLDER'], os.path.basename(filename))
            try:
                os.remove(path)
            except OSError:
                pass  # already gone, or never stored

        return jsonify({
            'deleted': True,
            'scans': scan_count,
            'chats': chat_count,
        })

    return jsonify({
        'scans': recent_scans(user_id=user_id, limit=12),
        'chats': recent_chats(user_id=user_id, limit=40),
        'requires_login': False,
    })


@app.route('/api/scans/<int:scan_id>', methods=['GET', 'DELETE'])
def scan_detail(scan_id):
    user_id = current_user_id()
    if user_id is None:
        return jsonify({'error': 'Please log in to view saved scans.'}), 401

    if request.method == 'DELETE':
        try:
            filename = delete_scan(scan_id, user_id=user_id)
        except Exception:
            return jsonify({'error': 'Could not delete this scan. Please try again.'}), 500

        if filename is None:
            return jsonify({'error': 'Scan not found'}), 404

        if filename:
            # basename() keeps a crafted database value from escaping the folder.
            path = os.path.join(app.config['UPLOAD_FOLDER'], os.path.basename(filename))
            try:
                os.remove(path)
            except OSError:
                pass  # already gone, or never stored

        return jsonify({'deleted': True, 'scan_id': scan_id})

    scan = get_scan(scan_id, user_id=user_id)
    if not scan:
        return jsonify({'error': 'Scan not found'}), 404

    if not scan['identified'] or not scan['predicted_soil']:
        return jsonify({
            'identified': False,
            'scan_id': scan['id'],
            'filename': scan['filename'],
            'confidence': scan['confidence'] or 0,
            'message': "This scan could not be identified with enough confidence.",
        })

    details = soil_details(scan['predicted_soil'])
    return jsonify({
        'identified': True,
        'scan_id': scan['id'],
        'filename': scan['filename'],
        'soil_type': details['display_name'],
        'confidence': scan['confidence'],
        **details,
    })


if __name__ == '__main__':
    app.run(debug=Config.DEBUG, port=5000)