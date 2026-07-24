import socketio

# Socket.io Async Sunucusu Oluşturma
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')

@sio.event
async def connect(sid, environ):
    print(f"[Socket.io] İstemci bağlandı: {sid}")

@sio.event
async def disconnect(sid):
    print(f"[Socket.io] İstemci ayrıldı: {sid}")
