from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect, text
from sqlalchemy import UniqueConstraint
from sqlalchemy.pool import StaticPool
from datetime import datetime, timedelta, timezone
import os
from urllib.request import urlopen
import uuid
import logging

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
database_url = os.getenv(
    'DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/workshop')
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JSON_SORT_KEYS'] = False
if database_url.startswith('sqlite'):
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'connect_args': {'check_same_thread': False},
        'poolclass': StaticPool,
    }

db = SQLAlchemy()
db.init_app(app)


def configure_database(uri):
    with app.app_context():
        app.config['SQLALCHEMY_DATABASE_URI'] = uri
        if uri.startswith('sqlite'):
            app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
                'connect_args': {'check_same_thread': False},
                'poolclass': StaticPool,
            }
        else:
            app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {}
        db.session.remove()
        if 'sqlalchemy' in app.extensions and not app.extensions['sqlalchemy'].engines:
            db.init_app(app)


@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-User-Id'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, DELETE, OPTIONS'
    return response


class WorkshopSession(db.Model):
    __tablename__ = 'workshop_sessions'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    start_time = db.Column(db.DateTime(timezone=True), nullable=False)
    duration_minutes = db.Column(db.Integer, nullable=False)
    capacity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    created_by = db.Column(db.String(64), nullable=False, default='admin')
    created_at = db.Column(db.DateTime(timezone=True),
                           server_default=db.func.now())
    updated_at = db.Column(db.DateTime(timezone=True),
                           server_default=db.func.now(), onupdate=db.func.now())


class Reservation(db.Model):
    __tablename__ = 'reservations'
    __table_args__ = (UniqueConstraint(
        'user_id', 'session_id', name='uq_user_session'),)

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey(
        'workshop_sessions.id'), nullable=False)
    student_name = db.Column(db.String(200), nullable=True)
    user_id = db.Column(db.String(64), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='confirmed')
    created_at = db.Column(db.DateTime(timezone=True),
                           server_default=db.func.now())
    cancelled_at = db.Column(db.DateTime(timezone=True), nullable=True)

    session = db.relationship('WorkshopSession', backref=db.backref(
        'reservations', cascade='all, delete-orphan'))


@app.before_request
def ensure_db():
    if request.path in ('/health', '/static', '/favicon.ico'):
        return None


@app.route('/<path:path>', methods=['OPTIONS'])
def options_handler(path):
    return '', 200


def init_db():
    with app.app_context():
        db.create_all()
        ensure_schema_compatibility()


def ensure_schema_compatibility():
    inspector = inspect(db.engine)

    session_columns = {
        column['name'] for column in inspector.get_columns('workshop_sessions')
    }
    if 'created_by' not in session_columns:
        db.session.execute(text(
            "ALTER TABLE workshop_sessions ADD COLUMN created_by VARCHAR(64) NOT NULL DEFAULT 'admin'"
        ))
        db.session.commit()

    reservation_columns = {
        column['name'] for column in inspector.get_columns('reservations')
    }
    if 'user_id' not in reservation_columns:
        db.session.execute(text(
            "ALTER TABLE reservations ADD COLUMN user_id VARCHAR(64)"
        ))
        if 'student_name' in reservation_columns:
            db.session.execute(text(
                "UPDATE reservations SET user_id = student_name WHERE user_id IS NULL"
            ))
        else:
            db.session.execute(text(
                "UPDATE reservations SET user_id = CAST(id AS VARCHAR(64)) WHERE user_id IS NULL"
            ))
        db.session.execute(text(
            "ALTER TABLE reservations ALTER COLUMN user_id SET NOT NULL"
        ))
        db.session.commit()

    if 'student_name' in reservation_columns:
        db.session.execute(text(
            "UPDATE reservations SET student_name = user_id WHERE student_name IS NULL AND user_id IS NOT NULL"
        ))
        db.session.commit()


@app.get('/health')
def health():
    return jsonify({'status': 'ok'})


def resolve_user_id(request_obj):
    header_value = (request_obj.headers.get('X-User-Id') or '').strip()
    if header_value:
        return header_value
    payload = request_obj.get_json(silent=True) or {}
    user_id = (payload.get('user_id') or '').strip()
    if user_id:
        return user_id
    return str(uuid.uuid4())


def notify(message):
    logging.info(message)


def fetch_online_uuid():
    with urlopen('https://www.uuidgenerator.net/api/version4', timeout=10) as response:
        return response.read().decode('utf-8').strip()


@app.post('/users/generate')
def generate_user_uuid():
    try:
        user_id = fetch_online_uuid()
    except Exception:
        user_id = str(uuid.uuid4())
    return jsonify({'user_id': user_id})


@app.get('/sessions')
def list_sessions():
    now = datetime.now(timezone.utc)
    sessions = WorkshopSession.query.filter(
        WorkshopSession.start_time >= now
    ).order_by(WorkshopSession.start_time.asc()).all()
    result = []
    for session in sessions:
        start_time = normalize_datetime(session.start_time)
        confirmed = [
            r for r in session.reservations if r.status == 'confirmed']
        waitlist = [r for r in session.reservations if r.status == 'waitlist']
        result.append({
            'id': session.id,
            'title': session.title,
            'start_time': start_time.isoformat(),
            'duration_minutes': session.duration_minutes,
            'capacity': session.capacity,
            'price': float(session.price),
            'confirmed_count': len(confirmed),
            'waitlist_count': len(waitlist),
            'is_ended': start_time <= now,
            'created_by': session.created_by,
        })
    return jsonify(result)


@app.post('/sessions')
def create_session():
    payload = request.get_json(silent=True) or {}
    required = ['title', 'start_time', 'duration_minutes', 'capacity', 'price']
    missing = [field for field in required if field not in payload]
    if missing:
        return jsonify({'error': f'Missing fields: {missing}'}), 400

    try:
        start_time = datetime.fromisoformat(
            payload['start_time'].replace('Z', '+00:00'))
    except Exception:
        return jsonify({'error': 'Invalid start_time'}), 400

    session = WorkshopSession(
        title=payload['title'],
        start_time=start_time,
        duration_minutes=int(payload['duration_minutes']),
        capacity=int(payload['capacity']),
        price=float(payload['price']),
        created_by='admin',
    )
    db.session.add(session)
    db.session.commit()
    notify(f'admin-created-session:{session.id}:admin')
    return jsonify({'id': session.id}), 201


@app.post('/sessions/<int:session_id>/reservations')
def reserve(session_id):
    payload = request.get_json(silent=True) or {}
    user_id = resolve_user_id(request)
    if not user_id:
        return jsonify({'error': 'user_id is required'}), 400

    session = WorkshopSession.query.get_or_404(session_id)
    start_time = normalize_datetime(session.start_time)
    if start_time <= datetime.now(timezone.utc):
        return jsonify({'error': 'This session has already ended'}), 400

    existing = Reservation.query.filter_by(
        session_id=session_id, user_id=user_id
    ).filter(Reservation.status.in_(['confirmed', 'waitlist'])).first()
    if existing:
        return jsonify({'error': 'User already reserved this session'}), 400

    confirmed_count = Reservation.query.filter_by(
        session_id=session_id, status='confirmed').count()
    if confirmed_count < session.capacity:
        reservation = Reservation(
            session_id=session_id,
            student_name=user_id,
            user_id=user_id,
            status='confirmed')
        db.session.add(reservation)
        db.session.commit()
        notify(f'user-reserved:{user_id}:{session_id}:confirmed')
        return jsonify({'status': 'confirmed', 'reservation_id': reservation.id}), 201

    reservation = Reservation(session_id=session_id,
                              student_name=user_id,
                              user_id=user_id, status='waitlist')
    db.session.add(reservation)
    db.session.commit()
    notify(f'user-reserved:{user_id}:{session_id}:waitlist')
    return jsonify({'status': 'waitlist', 'reservation_id': reservation.id}), 201


@app.delete('/reservations/<int:reservation_id>')
def cancel_reservation(reservation_id):
    reservation = Reservation.query.get_or_404(reservation_id)
    session = reservation.session
    start_time = normalize_datetime(session.start_time)

    if start_time <= datetime.now(timezone.utc):
        return jsonify({'error': 'This session has already ended'}), 400

    if reservation.status != 'confirmed':
        db.session.delete(reservation)
        db.session.commit()
        notify(f'user-cancelled:{reservation.user_id}:{reservation.id}')
        return jsonify({'status': 'cancelled'}), 200

    now = datetime.now(timezone.utc)
    if start_time - now > timedelta(hours=24):
        reservation.status = 'cancelled'
        db.session.commit()
        promote_waitlist(session.id)
        notify(f'user-cancelled:{reservation.user_id}:{reservation.id}')
        return jsonify({'status': 'cancelled'}), 200

    return jsonify({'error': 'Cannot cancel within 24 hours of the session'}), 400


@app.get('/reservations')
def list_reservations():
    user_id = resolve_user_id(request)
    reservations = Reservation.query.filter_by(user_id=user_id).order_by(
        Reservation.created_at.asc()).all()
    return jsonify([{
        'id': r.id,
        'session_id': r.session_id,
        'user_id': r.user_id,
        'status': r.status,
        'created_at': r.created_at.isoformat(),
    } for r in reservations])


def normalize_datetime(value):
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def promote_waitlist(session_id):
    session = WorkshopSession.query.get(session_id)
    if not session:
        return

    confirmed_count = Reservation.query.filter_by(
        session_id=session_id, status='confirmed').count()
    if confirmed_count >= session.capacity:
        return

    waitlist = Reservation.query.filter_by(
        session_id=session_id, status='waitlist').order_by(Reservation.created_at.asc()).all()
    if not waitlist:
        return

    first = waitlist[0]
    first.status = 'confirmed'
    db.session.add(first)
    db.session.commit()


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
