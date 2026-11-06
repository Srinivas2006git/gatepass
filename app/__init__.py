import os
from flask import Flask
from dotenv import load_dotenv
from config import Config
from .extensions import csrf, db, limiter, login_manager, migrate


def create_app(config_object=Config):
    load_dotenv()
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_object)
    os.makedirs(app.instance_path, exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    limiter.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "warning"

    from .models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    from .routes.admin import admin_bp
    from .routes.auth import auth_bp
    from .routes.main import main_bp
    from .routes.passes import passes_bp
    from .routes.security import security_bp
    from .routes.students import students_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(students_bp, url_prefix="/students")
    app.register_blueprint(passes_bp, url_prefix="/passes")
    app.register_blueprint(security_bp, url_prefix="/security")

    from .utils.timezone import format_india
    app.jinja_env.filters["india_time"] = format_india

    @app.cli.command("seed-admin")
    def seed_admin():
        from .models import Role, User
        for name in ("SUPER_ADMIN", "APPROVER", "STAFF", "SECURITY"):
            if not Role.query.filter_by(name=name).first():
                db.session.add(Role(name=name, display_name=name.replace("_", " ").title()))
        db.session.flush()
        if not User.query.filter_by(username="admin").first():
            admin = User(username="admin", full_name="System Administrator", email="admin@mrit.edu.in")
            admin.set_password("ChangeMe!2026")
            admin.roles.append(Role.query.filter_by(name="SUPER_ADMIN").one())
            db.session.add(admin)
        db.session.commit()
        print("Seeded roles and admin account. Change the default password immediately.")

    return app
