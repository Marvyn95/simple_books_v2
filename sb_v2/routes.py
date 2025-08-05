from sb_v2 import app, db, bcrypt
from flask import render_template, request, flash, redirect, url_for, session
import json, secrets, datetime
from bson.objectid import ObjectId


@app.route('/home')
def home():
    user = db.Users.find_one({"_id": ObjectId(session.get("userid"))})
    user["_id"] = str(user["_id"])
    organization = db.Organizations.find_one({"_id": user["organization_id"]})
    employees = list(db.Users.find({"organization_id": user["organization_id"]}))
    stock_items = list(db.Stock.find({"organization_id": user["organization_id"]}))
    
    for k in stock_items:
        for j in organization["branches"]:
            if k["branch_id"] == j["_id"]:
                k["branch"] = j["branch"]
    
    for i in employees:
        branch_objects = []
        for j in i["branch_ids"]:
            for m in organization["branches"]:
                if m["_id"] == j:
                    branch_objects.append(m)
        i["branches"] = branch_objects    

    branches = []
    for k in user["branch_ids"]:
        for j in organization["branches"]:
            if k == j["_id"]:
                branches.append(j)

    return render_template("home.html", 
                           year = datetime.datetime.today().year,
                           user = user,
                           organization = organization,
                           branches = branches,
                           employees = list(employees),
                           stock_items = stock_items)

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
                        "branch_ids": [],
                        "active_status": True
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
        if user["active_status"] == True:
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
            flash("Account was deactivated, contact your manager!")
            return redirect(url_for("login"))
            
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
    # getting initial user and organization info
    old_user_info = db.Users.find_one({"_id": ObjectId(session.get("userid"))})
    old_organization_info = db.Organizations.find_one({"_id": old_user_info["organization_id"]})

    # updating user name
    if form_info['username'] != old_user_info['username']:
        if db.Users.find_one({"username": form_info["username"]}) is None:
            db.Users.update_one({"_id": ObjectId(session.get("userid"))}, {
                "$set": {"username": form_info["username"]}
            })
        else:
            flash("User Name Already Taken, Use Another")
    
    # updating email
    if form_info['email'] != old_user_info['email']:
        if db.Users.find_one({"email": form_info["email"]}) is None:
            db.Users.update_one({"_id": ObjectId(session.get("userid"))}, {
                "$set": {"email": form_info["email"]}
            })
        else:
            flash("Email Already Taken, Use Another")

    #updating organization name
    if form_info['organization'] != old_organization_info['organization']:
        if db.Organizations.find_one({"organization": form_info["organization"]}) is None:
            db.Organizations.update_one({"_id": old_organization_info["_id"]}, {
                "$set": {"organization": form_info["organization"]}
            })
        else:
            flash("Organization Name Already Taken, Use Another")
    
    return redirect(url_for("home"))


@app.route("/add_branch", methods=['POST'])
def add_branch():
    form_info = request.form
    user = db.Users.find_one({"_id": ObjectId(session.get("userid"))})
    if user["role"] == "Manager":
        db.Organizations.update_one({"_id": user["organization_id"]}, {
            "$push": {"branches": {
                "_id": secrets.token_hex(32),
                "branch": form_info["branch_name"]
            }}
        })
    return redirect(url_for("home"))

@app.route("/edit_branch", methods=['POST'])
def edit_branch():
    form_info = request.form
    user = db.Users.find_one({"_id": ObjectId(session.get("userid"))})
    if user["role"] == "Manager":
        db.Organizations.update_one({"_id": user["organization_id"], "branches._id": form_info["branch_id"]}, {
            "$set": {"branches.$.branch": form_info["branch_name"]}
        })
    return redirect(url_for("home"))


@app.route("/edit_employee)", methods=['POST'])
def edit_employee():
    form_info = request.form
    # getting initial user and organization info
    user_info = db.Users.find_one({"_id": ObjectId(form_info["employee_id"])})
    if db.Users.find_one({"_id": ObjectId(session.get("userid"))})["role"] == "Manager":
        # updating user name
        if form_info['username'] != user_info['username']:
            if db.Users.find_one({"username": form_info["username"]}) is None:
                db.Users.update_one({"_id": ObjectId(form_info["employee_id"])}, {
                    "$set": {"username": form_info["username"]}
                })
            else:
                flash("User Name Already Taken, Use Another")
                
        # updating email
        if form_info['email'] != user_info['email']:
            if db.Users.find_one({"email": form_info["email"]}) is None:
                db.Users.update_one({"_id": ObjectId(form_info["employee_id"])}, {
                    "$set": {"email": form_info["email"]}
                })
            else:
                flash("Email Already Taken, Use Another")
        
        # updating role
        db.Users.update_one({"_id": ObjectId(form_info["employee_id"])}, {
                "$set": {"role": form_info.get("role")}
            })

        # updating branch id
        if user_info["role"] != "Manager":   
            db.Users.update_one({"_id": ObjectId(form_info["employee_id"])}, {
                    "$set": {"branch_ids": [form_info.get("branch_id")]}
                })    
        return redirect(url_for("home"))
    else:
        flash("Only Managers can update these details", "error")
        return redirect(url_for("home"))

@app.route("/deactivate_employee)", methods=['POST'])
def deactivate_employee():
    form_info = request.form
    db.Users.update_one({"_id": ObjectId(form_info["employee_id"])}, {
            "$set": {"active_status": False}
        })
    return redirect(url_for("home"))

@app.route("/activate_employee)", methods=['POST'])
def activate_employee():
    form_info = request.form
    db.Users.update_one({"_id": ObjectId(form_info["employee_id"])}, {
            "$set": {"active_status": True}
        })
    return redirect(url_for("home"))

@app.route("/add_employee)", methods=['POST'])
def add_employee():
    user = db.Users.find_one({"_id": ObjectId(session.get("userid"))})
    form_info = request.form
    if db.Users.find_one({"username": form_info["username"]}) is None:
        if form_info["password"] == form_info["confirm_password"]:
            db.Users.insert_one({
                "username": form_info["username"],
                "email": form_info["email"],
                "password": bcrypt.generate_password_hash(form_info["password"]).decode("utf-8"),
                "role": form_info["role"],
                "organization_id": user["organization_id"],
                "branch_ids": [form_info.get("branch_id")],
                "active_status": True
            })
            flash("Employee registered successfully!", "success")
            return redirect(url_for("home"))
        else:
            flash("Password mismatch!", "error")
            return redirect(url_for("home"))
    else:
        flash("User name already taken, use another!", "error")
        return redirect(url_for("home"))
    s
    
@app.route("/add_stock_item)", methods=['POST'])
def add_stock_item():
    form_info = request.form
    user = db.Users.find_one({"_id": ObjectId(form_info["user_id"])})
    if user["role"] == "Manager" or user["role"] == "Branch Manager":
        db.Stock.insert_one({
            "name": form_info["name"],
            "quantity": 0,
            "price": 0,
            "branch_id": form_info["branch_id"],
            "organization_id": user["organization_id"]
        })
        flash("Item added successfully!", "success")
        return redirect(url_for("home"))
    else:
        flash("Only Managers and Branch Managers can add new stock")
        return redirect(url_for("home"))
    

@app.route("/edit_stock_item)", methods=['POST'])
def edit_stock_item():
    form_info = request.form
    user = db.Users.find_one({"_id": ObjectId(session.get("userid"))})
    if user["role"] == "Manager":
        db.Stock.update_one({"_id": ObjectId(form_info["item_id"])}, {
            "$set": {"name": form_info["name"], "price": form_info["price"]}
        })
    elif user["role"] == "Branch Manager":
        db.Stock.update_one({"_id": ObjectId(form_info["item_id"])}, {
            "$set": {"name": form_info["name"]}
        })
    return redirect(url_for("home"))


@app.route("/update_stock_quantity)", methods=['POST'])
def update_stock_quantity():
    form_info = request.form
    user = db.Users.find_one({"_id": ObjectId(session.get("userid"))})
    if user["role"] == "Manager" or user["role"] == "Branch Manager":
        db.Stock.update_one({"_id": ObjectId(form_info["item_id"])}, {
            "$inc": {"quantity": int(form_info["quantity"])}
        })
        flash("Quantity updated successfully!", "success")
        return redirect(url_for("home"))
    else:
        flash("Sales Personnel cannot update stock", "error")
        return redirect(url_for("home"))
        