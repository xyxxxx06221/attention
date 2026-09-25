"""Disposable local UI verification; fixture data is never used by the release launcher."""
from review_ui import app, seed
app.PORT=8880
seed()
server=app.ThreadingHTTPServer(('127.0.0.1',8880),app.Handler)
print('UI verification http://127.0.0.1:8880',flush=True)
server.serve_forever()
