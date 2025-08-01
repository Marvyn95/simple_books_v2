from sb_v2 import app, db, bcrypt
from flask import render_template, request, flash, redirect, url_for, session
import json, secrets, datetime
from bson.objectid import ObjectId


@app.route('/home')
def home():
    user = db.Users.find_one({"_id": ObjectId(session.get("userid"))})
    organization = db.Organizations.find_one({"_id": user["organization_id"]})

    branches = []
    for k in user["branch_ids"]:
        for j in organization["branches"]:
            if k == j["_id"]:
                branches.append(j)

    return render_template("home.html", 
                           year = datetime.datetime.today().year,
                           user = user,
                           organization = organization,
                           branches = branches)

@app.route("/register_owner", methods=["GET", "POST"])
def register_owner():

    with open("../config.json") as config_file:
        config = json.load(config_file)

    if request.method == "POST":
        form_info = request.form
        if form_info["admin_password"] == config["ADMIN_PASSWORD"]:
            if db.Users.find_one({"username": form_info["username"]}) is None:
                if db.Organizations.find_one({"organization": form_info["organization"]}) is None:
                    db.Organizations.insert_one({
                        "organization": form_info["organization"],
                        "branches": [{"_id": secrets.token_hex(32), "branch": branch} for branch in request.form.getlist("branches") if branch != ""]
                    })
                    org = db.Organizations.find_one({"organization": form_info["organization"]})
                    db.Users.insert_one({
                        "username": form_info["username"],
                        "email": form_info["email"],
                        "password": bcrypt.generate_password_hash(form_info["password"]).decode("utf-8"),
                        "role": "Manager",
                        "organization_id": org["_id"],
                        "branch_ids": [i["_id"] for i in org["branches"] ] 
                    })
                    flash("You have been registered successfully!", "success")
                    return redirect(url_for("login"))
                else:
                    flash("Business/Organization already registered!", "error")
                    return redirect(url_for("register_owner"))
            else:
                flash("User name already taken, use another!", "error")
                return redirect(url_for("register_owner"))
        else:
                flash("Incorrect Administrator Password", "error")
                return redirect(url_for("register_owner"))
    else:
        return render_template("register_owner.html")
    

@app.route("/", methods=["GET", "POST"])
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        form_info = request.form
        user = db.Users.find_one({"username": form_info["username"]})
        if user:
            if bcrypt.check_password_hash(user["password"], form_info["password"]):
                session["userid"] = str(user["_id"])
                flash("Successful login!", "success")
                return redirect(url_for('home'))
            else:
                flash("Incorrect password!", "error")
                return redirect(url_for('login'))
        else:
            flash("That user name is not registered, try again!", "error")
        return redirect(url_for('login')) 
    else:  
        return render_template("login.html")

@app.route("/logout")
@app.route("/logout")
def logout():
    session.clear()
    flash("Log out successfull!", "info")
    return redirect(url_for("login"))

@app.route('/edit_profile', methods=['POST'])
def edit_profile():
    form_info = request.form
    old_user_info = db.Users.find_one({"_id": ObjectId(session.get("userid"))})
    old_organization_info = db.Organizations.find_one({"_id": old_user_info["organization_id"]})

    if form_info['username'] != old_user_info['username']:
        if db.Users.find_one({"username": form_info["username"]}) is None:
            db.Users.update_one({"_id": ObjectId(session.get("userid"))}, {
                "$set": {"username": form_info["username"]}
            })
        else:
            flash("User Name Already Taken, Use Another")
    
    if form_info['email'] != old_user_info['email']:
        if db.Users.find_one({"email": form_info["email"]}) is None:
            db.User.update_one({"_id": ObjectId(session.get("userid"))}, {
                "$set": {"email": form_info["email"]}
            })
        else:
            flash("Email Already Taken, Use Another")

    if request.form.getlist("branches") != old_user_info["branch_ids"]:
        db.Organizations.update_one({"_id": old_organization_info["_id"]}, {
            "$set": {"branch_ids": [b for b in request.form.getlist("branches") if b != ""]}
        })
    
    if form_info['organization'] != old_organization_info['organization']:
        if db.Organizations.find_one({"organization": form_info["organization"]}) is None:
            db.Organizations.update_one({"_id": old_organization_info["_id"]}, {
                "$set": {"organization": form_info["organization"]}
            })
        else:
            flash("Organization Name Already Taken, Use Another")
    
    return redirect(url_for("home"))
