from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import UniqueConstraint
from sqlalchemy.pool import StaticPool
from datetime import datetime, timedelta, timezone
import os

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
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
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
    created_at = db.Column(db.DateTime(timezone=True),
                           server_default=db.func.now())
    updated_at = db.Column(db.DateTime(timezone=True),
                           server_default=db.func.now(), onupdate=db.func.now())


class Reservation(db.Model):
    __tablename__ = 'reservations'
    __table_args__ = (UniqueConstraint(
        'student_name', 'session_id', name='uq_student_session'),)

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey(
        'workshop_sessions.id'), nullable=False)
    student_name = db.Column(db.String(200), nullable=False)
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


@app.get('/health')
def health():
    return jsonify({'status': 'ok'})


@app.get('/sessions')
def list_sessions():
    now = datetime.now(timezone.utc)
    sessions = WorkshopSession.query.filter(
        normalize_datetime(WorkshopSession.start_time) >= now
    ).order_by(WorkshopSession.start_time.asc()).all()
    result = []
    for session in sessions:
        confirmed = [
            r for r in session.reservations if r.status == 'confirmed']
        waitlist = [r for r in session.reservations if r.status == 'waitlist']
        result.append({
            'id': session.id,
            'title': session.title,
            'start_time': session.start_time.isoformat(),
            'duration_minutes': session.duration_minutes,
            'capacity': session.capacity,
            'price': float(session.price),
            'confirmed_count': len(confirmed),
            'waitlist_count': len(waitlist),
            'is_ended': session.start_time <= datetime.now(timezone.utc),
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
    )
    db.session.add(session)
    db.session.commit()
    return jsonify({'id': session.id}), 201


@app.post('/sessions/<int:session_id>/reservations')
def reserve(session_id):
    payload = request.get_json(silent=True) or {}
    student_name = (payload.get('student_name') or '').strip()
    if not student_name:
        return jsonify({'error': 'student_name is required'}), 400

    session = WorkshopSession.query.get_or_404(session_id)
    start_time = normalize_datetime(session.start_time)
    if start_time <= datetime.now(timezone.utc):
        return jsonify({'error': 'This session has already ended'}), 400

    existing = Reservation.query.filter_by(
        session_id=session_id, student_name=student_name
    ).filter(Reservation.status.in_(['confirmed', 'waitlist'])).first()
    if existing:
        return jsonify({'error': 'Student already reserved this session'}), 400

    session = WorkshopSession.query.filter_by(id=session_id).one()
    confirmed_count = Reservation.query.filter_by(
        session_id=session_id, status='confirmed').count()
    if confirmed_count < session.capacity:
        reservation = Reservation(
            session_id=session_id, student_name=student_name, status='confirmed')
        db.session.add(reservation)
        db.session.commit()
        return jsonify({'status': 'confirmed', 'reservation_id': reservation.id}), 201

    reservation = Reservation(session_id=session_id,
                              student_name=student_name, status='waitlist')
    db.session.add(reservation)
    db.session.commit()
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
        return jsonify({'status': 'cancelled'}), 200

    now = datetime.now(timezone.utc)
    if start_time - now > timedelta(hours=24):
        reservation.status = 'cancelled'
        db.session.commit()
        promote_waitlist(session.id)
        return jsonify({'status': 'cancelled'}), 200

    return jsonify({'error': 'Cannot cancel within 24 hours of the session'}), 400


@app.get('/reservations')
def list_reservations():
    reservations = Reservation.query.order_by(
        Reservation.created_at.asc()).all()
    return jsonify([{
        'id': r.id,
        'session_id': r.session_id,
        'student_name': r.student_name,
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
