from flask import Blueprint, flash, redirect, render_template, request, url_for
from ..extensions import db
from ..models import Department, Role, User
from ..utils.audit import record
from ..utils.permissions import roles_required

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/users", methods=["GET", "POST"])
@roles_required("SUPER_ADMIN")
def users():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        if User.query.filter_by(username=username).first():
            flash("Username already exists.", "danger")
        else:
            user = User(username=username, full_name=request.form.get("full_name", "").strip(), email=request.form.get("email", "").strip())
            user.set_password(request.form.get("password", ""))
            for role_id in request.form.getlist("roles"):
                role = db.session.get(Role, int(role_id))
                if role:
                    user.roles.append(role)
            db.session.add(user)
            record("USER_CREATED", "user", username)
            db.session.commit()
            flash("User created.", "success")
            return redirect(url_for("admin.users"))
    return render_template("admin/users.html", users=User.query.order_by(User.full_name).all(), roles=Role.query.order_by(Role.name).all())


@admin_bp.route("/departments", methods=["GET", "POST"])
@roles_required("SUPER_ADMIN")
def departments():
    if request.method == "POST":
        code, name = request.form.get("code", "").upper().strip(), request.form.get("name", "").strip()
        if code and name and not Department.query.filter((Department.code == code) | (Department.name == name)).first():
            db.session.add(Department(code=code, name=name))
            db.session.commit()
            flash("Department added.", "success")
        else:
            flash("Use a unique department code and name.", "danger")
    return render_template("admin/departments.html", departments=Department.query.order_by(Department.code).all())

