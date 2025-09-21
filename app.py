from flask import Flask, request, jsonify, g, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import uuid
import datetime

app = Flask(__name__, template_folder="templates")
app.config['SECRET_KEY'] = 'dev-secret-change-in-prod'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///chat.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

CORS(app, resources={r"/*": {"origins": "*"}})  # allow fetch from other origins (helpful during dev)
db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# ---------- DB models ----------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    token = db.Column(db.String(36), unique=True, nullable=False)
    lat = db.Column(db.Float, nullable=True)
    lon = db.Column(db.Float, nullable=True)
    last_seen = db.Column(db.DateTime, default=datetime.datetime.utcnow)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)

with app.app_context():
    db.create_all()

# ---------- Helpers ----------
def get_user_from_token(token):
    if not token:
        return None
    return User.query.filter_by(token=token).first()

@app.before_request
def load_user():
    auth = request.headers.get('Authorization', '')
    token = None
    if auth.startswith('Bearer '):
        token = auth[7:]
    # also allow token in query param for socket connects (handled separately)
    g.user = get_user_from_token(token)

# ---------- REST endpoints ----------
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['POST'])
def register():
    data = request.json or {}
    username = data.get('username')
    if not username:
        return jsonify({'error': 'username required'}), 400
    if User.query.filter_by(username=username).first():
        return jsonify({'error': 'username taken'}), 400
    token = str(uuid.uuid4())
    user = User(username=username, token=token)
    db.session.add(user)
    db.session.commit()
    return jsonify({'id': user.id, 'username': user.username, 'token': user.token})

@app.route('/me', methods=['GET'])
def me():
    if not g.user:
        return jsonify({'error':'unauthenticated'}), 401
    u = g.user
    return jsonify({
        'id': u.id,
        'username': u.username,
        'lat': u.lat,
        'lon': u.lon,
        'last_seen': u.last_seen.isoformat() if u.last_seen else None
    })

@app.route('/update_location', methods=['POST'])
def update_location():
    # Authorization via header / g.user
    if not g.user:
        return jsonify({'error': 'unauthenticated'}), 401
    data = request.json or {}
    lat = data.get('lat')
    lon = data.get('lon')
    if lat is None or lon is None:
        return jsonify({'error': 'lat & lon required'}), 400
    g.user.lat = float(lat)
    g.user.lon = float(lon)
    g.user.last_seen = datetime.datetime.utcnow()
    db.session.commit()
    # broadcast location update with consistent field names
    socketio.emit('location_update', {
        'id': g.user.id,
        'username': g.user.username,
        'lat': g.user.lat,
        'lon': g.user.lon
    }, broadcast=True)
    return jsonify({'status': 'ok'})

@app.route('/users', methods=['GET'])
def get_users():
    users = User.query.all()
    out = []
    for u in users:
        out.append({
            'id': u.id,
            'username': u.username,
            'lat': u.lat,
            'lon': u.lon,
            'last_seen': u.last_seen.isoformat() if u.last_seen else None
        })
    return jsonify(out)

@app.route('/messages/<int:with_user_id>', methods=['GET'])
def get_messages(with_user_id):
    if not g.user:
        return jsonify({'error': 'unauthenticated'}), 401
    msgs = Message.query.filter(
        ((Message.sender_id == g.user.id) & (Message.receiver_id == with_user_id)) |
        ((Message.sender_id == with_user_id) & (Message.receiver_id == g.user.id))
    ).order_by(Message.timestamp.asc()).all()
    return jsonify([{
        'id': m.id,
        'from': m.sender_id,
        'to': m.receiver_id,
        'content': m.content,
        'timestamp': m.timestamp.isoformat()
    } for m in msgs])

# ---------- Socket.IO realtime ----------
connected_users = {}   # user_id -> sid
sid_to_user = {}       # sid -> user_id

@socketio.on('connect')
def on_connect():
    # try to get token from query string or from Authorization header
    token = request.args.get('token')
    if not token:
        auth = request.headers.get('Authorization', '')
        if auth.startswith('Bearer '):
            token = auth[7:]
    user = get_user_from_token(token)
    if not user:
        # reject connection
        return False
    sid = request.sid
    connected_users[user.id] = sid
    sid_to_user[sid] = user.id

    # let all clients know someone connected (include lat/lon if available)
    emit('user_connected', {
        'id': user.id,
        'username': user.username,
        'lat': user.lat,
        'lon': user.lon
    }, broadcast=True)

    # send the currently connected users only to this client
    payload = []
    for uid, s in connected_users.items():
        u = User.query.get(uid)
        if u:
            payload.append({'id': u.id, 'username': u.username, 'lat': u.lat, 'lon': u.lon})
    emit('initial_users', payload, room=sid)

@socketio.on('disconnect')
def on_disconnect():
    sid = request.sid
    user_id = sid_to_user.get(sid)
    if user_id:
        connected_users.pop(user_id, None)
        sid_to_user.pop(sid, None)
        emit('user_disconnected', {'id': user_id}, broadcast=True)

@socketio.on('private_message')
def handle_private_message(data):
    sid = request.sid
    sender_id = sid_to_user.get(sid)
    if not sender_id:
        emit('error', {'error': 'unauthenticated'})
        return
    to = data.get('to')
    content = data.get('content', '')
    if not to or content is None:
        emit('error', {'error': 'invalid payload'})
        return
    # ensure integer
    try:
        to_id = int(to)
    except Exception:
        emit('error', {'error': 'invalid recipient id'})
        return
    msg = Message(sender_id=sender_id, receiver_id=to_id, content=content)
    db.session.add(msg)
    db.session.commit()
    payload = {
        'id': msg.id,
        'from': msg.sender_id,
        'to': msg.receiver_id,
        'content': msg.content,
        'timestamp': msg.timestamp.isoformat()
    }
    recipient_sid = connected_users.get(to_id)
    if recipient_sid:
        # send to recipient
        socketio.emit('new_message', payload, room=recipient_sid)
    # notify sender that message was sent + return the payload to sender
    emit('message_sent', payload)

if __name__ == '__main__':
    # eventlet is recommended for production; for dev the default is fine
    socketio.run(app, host='0.0.0.0', port=5001, debug=True)