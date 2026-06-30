from datetime import timedelta

from flask import Flask

from database.database import init_db
from modem.manager import ModemManager
from services.sync_service import SyncService
from utils.config import LOG_DIR, get_app_config
from utils.logger import setup_logging
from web.auth import auth_bp
from web.routes import main_bp


def create_app(start_workers: bool = True) -> Flask:
    config = get_app_config()
    setup_logging(config.get("log_level", "INFO"))
    init_db()

    app = Flask(__name__)
    app.secret_key = config.get("secret_key", "change-this-secret-key")
    app.permanent_session_lifetime = timedelta(minutes=int(config.get("session_timeout_minutes", 60)))
    app.config["LOG_PATH"] = LOG_DIR / "app.log"

    manager = ModemManager()
    sync_service = SyncService(manager)
    app.extensions["modem_manager"] = manager
    app.extensions["sync_service"] = sync_service

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)

    if start_workers:
        manager.start()
        sync_service.start()

    return app


app = create_app(start_workers=True)


if __name__ == "__main__":
    config = get_app_config()
    app.run(host=config.get("host", "0.0.0.0"), port=int(config.get("port", 5000)))
