from sb_v2 import app
from flask import render_template, request
import json


@app.route('/')
def home():
    return render_template("home.html")

@app.route("/register_owner", methods=["GET", "POST"])
def register_owner():
    with open("../config.json") as config_file:
        config = json.load(config_file)

    if request.method == "POST":
        form_info = request.form
        if form_info["admin_password"] == config["ADMIN_PASSWORD"]:
            
            return render_template("register_owner_success.html")
    else:
        return render_template("register_owner.html")
