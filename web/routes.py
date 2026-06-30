import logging
import os
import time

from flask import Blueprint, Response, current_app, flash, redirect, render_template, request, send_file, url_for

from database import modem as modem_db
from database.at_history import add_at_history, recent_at_history
from database.mail import recent_mail_logs
from database.sms import delete_sms, export_sms_rows, get_sms, list_sms, update_read_state
from services.mail_service import MailService
from services.stats_service import (
    backup_database,
    dashboard_stats,
    database_stats,
    delete_sms_older_than,
    integrity_check,
    keep_latest_sms,
    restore_database,
    vacuum_database,
)
from utils.config import get_app_config, get_mail_config, save_app_config, save_mail_config
from utils.exporter import rows_to_csv, rows_to_json
from utils.security import clean_port, login_required, safe_int

LOGGER = logging.getLogger(__name__)
main_bp = Blueprint("main", __name__)


def get_manager():
    return current_app.extensions.get("modem_manager")


@main_bp.route("/")
@login_required
def dashboard():
    return render_template("dashboard.html", stats=dashboard_stats(), modems=modem_db.list_modems())


@main_bp.route("/modems", methods=["GET", "POST"])
@login_required
def modems():
    manager = get_manager()
    if request.method == "POST":
        action = request.form.get("action")
        if action == "add":
            port = clean_port(request.form.get("port", ""))
            remark = request.form.get("remark", "").strip()
            if not port:
                flash("串口格式无效", "danger")
            else:
                modem_db.add_modem(port, remark or port)
                if manager:
                    manager.reload()
                flash("模块已添加并保存", "success")
        elif action == "remark":
            modem_db.update_remark(request.form.get("module_id", ""), request.form.get("remark", "").strip())
            flash("备注已保存", "success")
        elif action == "delete":
            modem_db.delete_modem(request.form.get("module_id", ""))
            if manager:
                manager.reload()
            flash("模块已删除", "success")
        elif action == "enable":
            modem_db.set_enabled(request.form.get("module_id", ""), True)
            if manager:
                manager.reload()
            flash("模块已启用", "success")
        elif action == "disable":
            modem_db.set_enabled(request.form.get("module_id", ""), False)
            if manager:
                manager.reload()
            flash("模块已禁用", "warning")
        elif action == "reboot":
            ok = manager.soft_reboot(request.form.get("module_id", "")) if manager else False
            flash("模块正在重启并重新初始化" if ok else "模块重启失败", "success" if ok else "danger")
        return redirect(url_for("main.modems"))
    return render_template("modems.html", modems=modem_db.list_modems())


@main_bp.route("/sms")
@login_required
def sms_records():
    config = get_app_config()
    page = safe_int(request.args.get("page"), 1, 1)
    page_size = safe_int(config.get("sms_page_size"), 20, 1, 200)
    filters = {
        "keyword": request.args.get("keyword", ""),
        "module_id": request.args.get("module_id", ""),
        "phone": request.args.get("phone", ""),
        "forwarded": request.args.get("forwarded", ""),
        "is_read": request.args.get("is_read", ""),
        "date_from": request.args.get("date_from", ""),
        "date_to": request.args.get("date_to", ""),
    }
    rows, total = list_sms(filters, page, page_size)
    return render_template(
        "sms.html",
        rows=rows,
        total=total,
        page=page,
        page_size=page_size,
        filters=filters,
        modems=modem_db.list_modems(),
    )


@main_bp.route("/sms/action", methods=["POST"])
@login_required
def sms_action():
    action = request.form.get("action")
    ids = [safe_int(item, 0) for item in request.form.getlist("ids")]
    ids = [item for item in ids if item]
    mail_service = MailService()
    if action == "resend_one":
        sms_id = safe_int(request.form.get("sms_id"), 0)
        ok = mail_service.send_for_sms(sms_id)
        flash("邮件重发成功" if ok else "邮件重发失败，请查看日志", "success" if ok else "danger")
    elif action == "resend" and ids:
        ok_count = sum(1 for item in ids if mail_service.send_for_sms(item))
        flash("已重发 {} 条".format(ok_count), "success")
    elif action == "read" and ids:
        update_read_state(ids, True)
        flash("已标记已读", "success")
    elif action == "unread" and ids:
        update_read_state(ids, False)
        flash("已标记未读", "success")
    elif action == "delete" and ids:
        delete_sms(ids)
        flash("已删除本地记录", "warning")
    return redirect(request.referrer or url_for("main.sms_records"))


@main_bp.route("/sms/export/<kind>")
@login_required
def sms_export(kind):
    rows = export_sms_rows()
    if kind == "csv":
        return Response(rows_to_csv(rows), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=sms.csv"})
    return Response(rows_to_json(rows), mimetype="application/json", headers={"Content-Disposition": "attachment; filename=sms.json"})


@main_bp.route("/manual-read", methods=["GET", "POST"])
@login_required
def manual_read():
    manager = get_manager()
    messages = []
    selected_module = request.form.get("module_id") or request.args.get("module_id", "")
    status = request.form.get("status") or request.args.get("status", "ALL")
    if request.method == "POST" and request.form.get("action") == "read" and manager:
        messages = manager.sms_service.read_module_messages_for_display(selected_module, status)
    elif request.method == "POST" and request.form.get("action") == "mail":
        message = {
            "phone": request.form.get("phone", ""),
            "content": request.form.get("content", ""),
            "receive_time": request.form.get("receive_time", ""),
            "modem_name": request.form.get("modem_name", ""),
        }
        ok = MailService().send_manual_message(message)
        flash("手动发送邮件成功" if ok else "手动发送邮件失败", "success" if ok else "danger")
    return render_template("manual_read.html", modems=modem_db.list_modems(), messages=messages, selected_module=selected_module, status=status)


@main_bp.route("/send-sms", methods=["GET", "POST"])
@login_required
def send_sms():
    manager = get_manager()
    if request.method == "POST":
        module_id = request.form.get("module_id")
        modem = manager.get_modem(module_id) if manager else None
        try:
            if not modem:
                raise RuntimeError("模块不可用")
            modem.send_sms(request.form.get("phone", ""), request.form.get("content", ""))
            flash("短信发送成功", "success")
        except Exception as exc:
            flash("短信发送失败：{}".format(exc), "danger")
    return render_template("send_sms.html", modems=modem_db.list_modems())


@main_bp.route("/mail", methods=["GET", "POST"])
@login_required
def mail_config():
    config = get_mail_config()
    if request.method == "POST":
        config.update(
            {
                "enabled": request.form.get("enabled") == "on",
                "smtp_server": request.form.get("smtp_server", ""),
                "port": safe_int(request.form.get("port"), 465, 1, 65535),
                "use_ssl": request.form.get("use_ssl") == "on",
                "use_tls": request.form.get("use_tls") == "on",
                "username": request.form.get("username", ""),
                "from_email": request.form.get("from_email", ""),
                "password": request.form.get("password") or config.get("password", ""),
                "recipients": [line.strip() for line in request.form.get("recipients", "").splitlines() if line.strip()],
                "subject_template": request.form.get("subject_template", ""),
                "body_template": request.form.get("body_template", ""),
                "timeout_seconds": safe_int(request.form.get("timeout_seconds"), 20, 3, 120),
            }
        )
        save_mail_config(config)
        if request.form.get("action") == "test":
            ok = MailService().send_message(config.get("recipients", []), "测试邮件", "这是一封测试邮件。")
            flash("测试发送成功" if ok else "测试发送失败", "success" if ok else "danger")
        else:
            flash("邮件配置已保存", "success")
    return render_template("mail.html", config=config, recipients="\n".join(config.get("recipients", [])), logs=recent_mail_logs())


@main_bp.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    config = get_app_config()
    if request.method == "POST":
        for key in ["log_level"]:
            config[key] = request.form.get(key, config.get(key, ""))
        for key in ["sms_page_size", "sync_interval_seconds", "heartbeat_interval_seconds", "reconnect_initial_seconds", "reconnect_max_seconds", "mail_timeout_seconds", "ui_refresh_seconds"]:
            config[key] = safe_int(request.form.get(key), int(config.get(key, 0)), 1)
        save_app_config(config)
        flash("系统设置已保存", "success")
    return render_template("settings.html", config=config)


@main_bp.route("/at", methods=["GET", "POST"])
@login_required
def at_debug():
    manager = get_manager()
    response = ""
    duration_ms = 0
    if request.method == "POST":
        module_id = request.form.get("module_id", "")
        command = request.form.get("command", "").strip()
        modem = manager.get_modem(module_id) if manager else None
        start = time.time()
        try:
            if not modem:
                raise RuntimeError("模块不可用")
            response = modem.send_at(command, timeout=15, wait_ok=True)
            duration_ms = int((time.time() - start) * 1000)
            add_at_history(module_id, command, response, duration_ms, True)
        except Exception as exc:
            response = str(exc)
            duration_ms = int((time.time() - start) * 1000)
            add_at_history(module_id, command, response, duration_ms, False)
    quick = ["ATI", "AT+CSQ", "AT+COPS?", "AT+CPIN?", "AT+CGSN", "AT+CGMM", "AT+CGMR", 'AT+CMGL="ALL"', "AT+CREG?", "AT+CGREG?", "AT+QCCID", "AT+CIMI"]
    return render_template("at.html", modems=modem_db.list_modems(), response=response, duration_ms=duration_ms, history=recent_at_history(), quick=quick)


@main_bp.route("/logs")
@login_required
def logs():
    log_path = current_app.config.get("LOG_PATH")
    lines = []
    if log_path and log_path.exists():
        with log_path.open("r", encoding="utf-8", errors="ignore") as file_obj:
            lines = file_obj.readlines()[-500:]
    return render_template("logs.html", lines=lines)


@main_bp.route("/logs/clear", methods=["POST"])
@login_required
def clear_logs():
    log_path = current_app.config.get("LOG_PATH")
    if log_path:
        log_path.write_text("", encoding="utf-8")
    flash("日志已清空", "success")
    return redirect(url_for("main.logs"))


@main_bp.route("/database", methods=["GET", "POST"])
@login_required
def database_page():
    result = ""
    if request.method == "POST":
        action = request.form.get("action")
        if action == "vacuum":
            vacuum_database()
            result = "数据库优化完成"
        elif action == "check":
            result = "完整性检查：{}".format(integrity_check())
        elif action == "backup":
            result = "备份完成：{}".format(backup_database())
        elif action == "cleanup_days":
            count = delete_sms_older_than(safe_int(request.form.get("days"), 0, 0))
            result = "已删除超过指定天数的短信：{} 条".format(count)
        elif action == "cleanup_count":
            count = keep_latest_sms(safe_int(request.form.get("max_count"), 0, 0))
            result = "已按数量清理短信：{} 条".format(count)
        elif action == "restore":
            file_obj = request.files.get("db_file")
            if file_obj and file_obj.filename:
                os.makedirs(current_app.instance_path, exist_ok=True)
                temp_path = current_app.instance_path + "/restore-upload.db"
                file_obj.save(temp_path)
                restore_database(temp_path)
                result = "数据库恢复完成，建议重启服务"
            else:
                result = "请选择数据库文件"
    return render_template("database.html", stats=database_stats(), result=result)
