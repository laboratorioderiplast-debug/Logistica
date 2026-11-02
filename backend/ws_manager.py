"""
Gestione dei canali WebSocket in tempo reale.

Due tipi di client si collegano:
  - 'office'      -> l'ufficio, riceve la lista dei nuovi LP e gli aggiornamenti di stato
  - 'tablet:<id>'  -> un magazziniere specifico, riceve l'LP assegnato a lui
"""

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self._connections: dict[str, list[WebSocket]] = {}

    async def connect(self, channel: str, websocket: WebSocket):
        await websocket.accept()
        self._connections.setdefault(channel, []).append(websocket)

    def disconnect(self, channel: str, websocket: WebSocket):
        if channel in self._connections and websocket in self._connections[channel]:
            self._connections[channel].remove(websocket)
            if not self._connections[channel]:
                del self._connections[channel]

    async def send_to_channel(self, channel: str, message: dict):
        for ws in list(self._connections.get(channel, [])):
            try:
                await ws.send_json(message)
            except Exception:
                self.disconnect(channel, ws)

    def is_online(self, channel: str) -> bool:
        return bool(self._connections.get(channel))


manager = ConnectionManager()
