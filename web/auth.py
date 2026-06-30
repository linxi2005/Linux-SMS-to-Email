from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from utils.config import get_app_config
from utils.security import verify_password

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    config = get_app_config()
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if username == config.get("admin_username") and verify_password(config.get("admin_password_hash", ""), password):
            session["logged_in"] = True
            session["username"] = username
            return redirect(request.args.get("next") or url_for("main.dashboard"))
        flash("用户名或密码错误", "danger")
    return render_template("login.html")


@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
