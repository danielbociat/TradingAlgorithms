from datetime import timedelta

from flask import Flask
from flask_jwt_extended import (
    JWTManager
)

import aws_connections
import endpoints
from trading_algorithms import *

pd.options.mode.chained_assignment = None  # default='warn'

# Application
application = Flask(__name__)
application.config["JWT_SECRET_KEY"] = aws_connections.get_secret_from_secrets_manager(aws_connections.SECRETS_MANAGER, "jwt_secret_key")
application.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=1)
jwt = JWTManager(application)

application.register_blueprint(endpoints.SWAGGER_BLUEPRINT, url_prefix=endpoints.SWAGGER_URL)

application.register_blueprint(endpoints.AUTH)
application.register_blueprint(endpoints.MISC)
application.register_blueprint(endpoints.ALGO)
application.register_blueprint(endpoints.STATS)

if __name__ == "__main__":
    application.run(debug=True)
