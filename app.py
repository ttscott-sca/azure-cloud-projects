"""Flask web app deployed to Azure App Service.

Endpoints
---------
/            Status page (HTML)
/health      Liveness check, used by App Service health check and the CI smoke test
/api/info    Basic runtime info as JSON

Monitoring: set ENABLE_AZURE_MONITOR=true and APPLICATIONINSIGHTS_CONNECTION_STRING
in the App Service configuration to send telemetry to Application Insights from the
code. It is off by default so it doesn't double up with portal auto-instrumentation.
"""

import logging
import os
import platform
import time
from datetime import datetime, timezone

from flask import Flask, jsonify, render_template

logger = logging.getLogger(__name__)

START_TIME = time.time()


def _setup_monitoring() -> bool:
    """Send telemetry to Application Insights when explicitly enabled.

    Must run before the Flask app is created so Flask gets instrumented.
    """
    if os.environ.get("ENABLE_AZURE_MONITOR", "").lower() != "true":
        return False
    connection_string = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING")
    if not connection_string:
        logger.warning("ENABLE_AZURE_MONITOR is true but no connection string is set")
        return False
    try:
        from azure.monitor.opentelemetry import configure_azure_monitor

        configure_azure_monitor(connection_string=connection_string)
        logger.info("Application Insights telemetry enabled")
        return True
    except Exception:  # monitoring must never stop the app from starting
        logger.exception("Could not enable Application Insights")
        return False


MONITORING_ENABLED = _setup_monitoring()

app = Flask(__name__)


def _runtime_info() -> dict:
    return {
        "app": os.environ.get("WEBSITE_SITE_NAME", "local"),
        "region": os.environ.get("REGION_NAME", "local"),
        "version": os.environ.get("APP_VERSION", "dev"),
        "python": platform.python_version(),
        "uptime_seconds": int(time.time() - START_TIME),
        "monitoring": "Application Insights" if MONITORING_ENABLED else "off",
        "server_time_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
    }


@app.route("/")
def home():
    return render_template("index.html", info=_runtime_info())


@app.route("/health")
def health():
    return jsonify(status="ok"), 200


@app.route("/api/info")
def info():
    return jsonify(_runtime_info())


@app.after_request
def add_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
    )
    return response


@app.errorhandler(404)
def not_found(_error):
    return jsonify(error="not found"), 404


@app.errorhandler(500)
def server_error(_error):
    logger.exception("Unhandled error")
    return jsonify(error="internal server error"), 500


if __name__ == "__main__":
    # Local development only. Azure runs the app with gunicorn.
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 5000)))
