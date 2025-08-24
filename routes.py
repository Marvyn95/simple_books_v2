from __init__ import app, db, bcrypt
from flask import render_template, request, flash, redirect, url_for, session, send_file
import pandas as pd
from io import BytesIO
import json, secrets, datetime
from bson.objectid import ObjectId
from collections import defaultdict
from datetime import timedelta


@app.route("/", methods=["GET", "POST"])
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    if request.method == "POST":
        form_info = request.form
        user = db.Users.find_one({"username": form_info["username"]})
        if user == None:
            flash("Account doesnt exist, check user name!", "error")
            return redirect(url_for("login"))
        
        if user.get("active_status") == False:
            flash("Account was deactivated, contact your manager!")
            return redirect(url_for("login"))

        if bcrypt.check_password_hash(user["password"], form_info["password"]) is False:
            flash("Incorrect password!", "error")
            return redirect(url_for("login"))

        # storing common useful info in sessions
        session["userid"] = str(user["_id"])

        if user.get("role") != "Manager":
            organization = db.Organizations.find_one({"_id": ObjectId(user.get("organization_id"))})
            session["branch"] =  next((item for item in organization.get("branches", []) if item["_id"] == user.get("branch_id")), None)

        flash("Successful login!", "success")
        return redirect(url_for("transactions"))




@app.route("/register", methods=["GET", "POST"])
def register():

    with open("../config.json") as config_file:
        config = json.load(config_file)

    if request.method == "GET":
        return render_template("register.html")

    if request.method == "POST":
        form_info = request.form

        if form_info.get("admin_password") != config.get("ADMIN_PASSWORD"):
            flash("Incorrect Administrator Password", "error")
            return redirect(url_for("register"))

        if form_info.get("password") != form_info.get("confirm_password"):
            flash("Passwords do not match", "error")
            return redirect(url_for("register"))

        if db.Organizations.find_one({"organization": form_info["organization"]}) is not None:
            flash("Business/Organization already registered!", "error")
            return redirect(url_for("register"))

        if db.Users.find_one({"username": form_info["username"]}) is not None:
            flash("User name already taken, use another!", "error")
            return redirect(url_for("register"))

        db.Organizations.insert_one({
            "organization": form_info.get("organization").strip(),
            "branches": [{"_id": secrets.token_hex(32), "branch": branch.strip()} for branch in request.form.getlist("branches") if branch != ""]
        })

        org = db.Organizations.find_one({"organization": form_info["organization"]})

        db.Users.insert_one({
            "username": form_info.get("username").strip(),
            "email": form_info.get("email").strip(),
            "password": bcrypt.generate_password_hash(form_info["password"]).decode("utf-8"),
            "role": "Manager",
            "organization_id": org.get("_id"),
            "branch_ids": [],
            "active_status": True
        })
        
        flash("You have been registered successfully!", "success")
        return redirect(url_for("login"))

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out successfully!", "success")
    return redirect(url_for("login"))



@app.route('/transactions')
def transactions():
    user = db.Users.find_one({"_id": ObjectId(session.get("userid"))})
    organization = db.Organizations.find_one({"_id": ObjectId(user.get("organization_id"))})
    user['organization'] = organization.get('organization')
    selected_branch = session.get("branch")

    return render_template('transactions.html', user=user, selected_branch=selected_branch, organization=organization)


@app.route('/change_branch', methods=["POST"])
def change_branch():
    organization_id = request.form.get("organization_id")
    branch_id = request.form.get("branch_id")

    if branch_id == "":
        session.pop("branch", None)
    else:
        for branch in db.Organizations.find_one({"_id": ObjectId(organization_id)}).get("branches", []):
            if str(branch.get("_id")) == str(branch_id):
                session["branch"] = branch
                break

    return redirect(request.referrer)


# profile
@app.route('/profile')
def profile():
    user = db.Users.find_one({"_id": ObjectId(session.get("userid"))})
    organization = db.Organizations.find_one({"_id": ObjectId(user.get("organization_id"))})
    user['organization'] = organization.get('organization')
    selected_branch = session.get("branch")

    return render_template('profile.html', user=user, selected_branch=selected_branch, organization=organization)



@app.route('/edit_profile', methods=['POST'])
def edit_profile():
    username = request.form.get('username').strip() if request.form.get('username') else None
    organization_name = request.form.get('organization').strip() if request.form.get('organization') else None
    user_id = session.get('userid')

    user = db.Users.find_one({"_id": ObjectId(user_id)})
    organization = db.Organizations.find_one({"_id": ObjectId(user.get("organization_id"))})

    if username != None: 
        if username != user.get("username") and db.Users.find_one({"username": username}) is not None:
            flash('Username already taken, please choose another.', 'error')
            return redirect(url_for('profile'))

    if organization_name != None: 
        if organization_name != organization.get("organization") and db.Organizations.find_one({"organization": organization_name}) is not None:
            flash('Organization name already taken, please choose another.', 'error')
            return redirect(url_for('profile'))

    if username != None:
        db.Users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"username": username}}
        )

    if organization_name != None:
        db.Organizations.update_one(
            {"_id": ObjectId(organization.get("_id"))},
            {"$set": {"organization": organization_name}}
        )

    flash('Profile updated successfully!', 'success')
    return redirect(url_for('profile'))



@app.route('/update_password', methods=['POST'])
def update_password():
    user_id = session.get('userid')
    password = request.form.get('password')
    confirm_password = request.form.get('confirm_password')

    if password != confirm_password:
        flash('Passwords do not match.', 'error')
        return redirect(url_for('profile'))
    
    db.Users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"password": bcrypt.generate_password_hash(password).decode("utf-8")}}
    )
    flash('Password updated successfully!', 'success')
    return redirect(url_for('profile'))



@app.route('/edit_branch', methods=['POST'])
def edit_branch():
    branch_id = request.form.get('branch_id')
    branch_name = request.form.get('branch')

    db.Organizations.update_one(
        {"branches._id": branch_id},
        {"$set": {"branches.$.branch": branch_name}}
    )
    flash('Branch updated successfully!', 'success')
    return redirect(url_for('profile'))



@app.route('/delete_branch', methods=['POST'])
def delete_branch():
    branch_id = request.form.get('branch_id')
    organization_id = request.form.get('organization_id')

    if len(list(db.Users.find({"branch_id": branch_id}))) > 0:
        flash('Branch cannot be deleted because it has users.', 'error')
        return redirect(url_for('profile'))

    db.Organizations.update_one(
        {"_id": ObjectId(organization_id)},
        {"$pull": {"branches": {"_id": branch_id}}}
    )
    flash('Branch deleted successfully!', 'success')
    return redirect(url_for('profile'))


@app.route('/add_branch', methods=['POST'])
def add_branch():
    organization_id = request.form.get('organization_id')
    user_id = request.form.get('user_id')
    branch_name = request.form.get('branch').strip()

    organization = db.Organizations.find_one({"_id": ObjectId(organization_id)})

    for b in organization.get("branches", []):
        if b.get("branch") == branch_name:
            flash('Branch already exists.', 'error')
            return redirect(url_for('profile'))

    new_branch = {
        "_id": secrets.token_hex(32),
        "branch": branch_name
    }

    db.Organizations.update_one(
        {"_id": ObjectId(organization_id)},
        {"$push": {"branches": new_branch}}
    )

    flash('Branch added successfully!', 'success')
    return redirect(url_for('profile'))






@app.route('/stock', methods=['GET'])
def stock():
    user = db.Users.find_one({"_id": ObjectId(session.get("userid"))})
    organization = db.Organizations.find_one({"_id": ObjectId(user.get("organization_id"))})
    user['organization'] = organization.get('organization')
    selected_branch = session.get("branch")
    branch = session.get("branch")

    if selected_branch is None:
        stock = list(db.Stock.find({"organization_id": ObjectId(organization.get("_id"))}))
        for item in stock:
            item['branch'] = next((b for b in organization.get("branches", []) if b.get("_id") == item.get("branch_id")), {}).get("branch")
    else:
        stock = list(db.Stock.find({"branch_id": branch.get("_id"), "organization_id": ObjectId(organization.get("_id"))}))
        for item in stock:
            item['branch'] = next((b for b in organization.get("branches", []) if b.get("_id") == item.get("branch_id")), {}).get("branch")

    return render_template('stock.html',
                           user=user,
                           selected_branch=selected_branch,
                           organization=organization,
                           branch=branch,
                           stock=stock)



@app.route('/add_item', methods=['POST'])
def add_item():
    name = request.form.get('name').strip()
    branch_id = request.form.get('branch_id')
    organization_id = request.form.get('organization_id')

    if len(list(db.Stock.find({"name": name, "branch": branch_id, "organization_id": ObjectId(organization_id)}))) > 0:
        flash('Item with the same name already exists in this branch.', 'error')
        return redirect(url_for('stock'))

    db.Stock.insert_one({
        "name": name,
        "branch_id": branch_id,
        "organization_id": ObjectId(organization_id),
        "quantity": int(0),
        "price": int(0)
    })
    flash('Item added successfully!', 'success')
    return redirect(url_for('stock'))



@app.route('/edit_item', methods=['POST'])
def edit_item():
    item_id = request.form.get('item_id')
    organization_id = request.form.get('organization_id')
    branch_id = request.form.get('branch_id')
    name = request.form.get('name').strip()
    price = int(request.form.get('price'))

    db.Stock.update_one(
        {"_id": ObjectId(item_id)},
        {"$set": {"name": name, "branch_id": branch_id, "price": price}}
    )

    flash('Item updated successfully!', 'success')
    return redirect(url_for('stock'))



@app.route('/update_stock', methods=['POST'])
def update_stock():
    item_id = request.form.get('item_id')
    quantity = int(request.form.get('quantity'))
    unit_cost = int(request.form.get('unit_cost'))
    organization_id = request.form.get('organization_id')
    updater_id = request.form.get('user_id')
    branch_id = request.form.get('branch_id')

    db.Stock_movement.insert_one({
            "date": datetime.datetime.now(),
            "organization_id": ObjectId(organization_id),
            "branch_id": branch_id,
            "updater_id": ObjectId(updater_id),
            "item_id": item_id,
            "quantity_updated": quantity,
            "unit_cost": unit_cost
        }
    )

    item = db.Stock.find_one({"_id": ObjectId(item_id)})
    db.Stock.update_one(
        {"_id": ObjectId(item_id)},
        {"$set": {
            "quantity": item.get("quantity") + quantity
        }}
    )   

    flash('Stock updated successfully!', 'success')
    return redirect(url_for('stock'))



@app.route('/delete_item', methods=['POST'])
def delete_item():
    item_id = request.form.get('item_id')
    
    if len(list(db.Sales.find({"item_id": item_id}))) > 0:
        flash('Item cannot be deleted because it has sales records.', 'error')
        return redirect(url_for('stock'))

    if len(list(db.Stock_movement.find({"item_id": item_id}))) > 0:
        flash('Item cannot be deleted because it has stock movement records.', 'error')
        return redirect(url_for('stock'))

    db.Stock.delete_one({"_id": ObjectId(item_id)})
    flash('Item deleted successfully!', 'success')
    return redirect(url_for('stock'))





# employees
@app.route('/employees')
def employees():
    user = db.Users.find_one({"_id": ObjectId(session.get("userid"))})
    organization = db.Organizations.find_one({"_id": ObjectId(user.get("organization_id"))})
    user['organization'] = organization.get('organization')
    selected_branch = session.get("branch")

    employees = list(db.Users.find({"organization_id": ObjectId(user.get("organization_id"))}))

    for e in employees:
        e['branch'] = next((item for item in organization.get("branches", []) if item["_id"] == e.get("branch_id")), {}).get("branch")

    return render_template('employees.html',
                           user=user,
                           selected_branch=selected_branch,
                           organization=organization,
                           employees=employees)



@app.route('/add_employee', methods=['POST'])
def add_employee():
    username = request.form.get('username').strip()
    password = request.form.get('password')
    confirm_password = request.form.get('confirm_password')
    role = request.form.get('role')
    branch_id = request.form.get('branch_id')
    organization_id = request.form.get('organization_id')

    if db.Users.find_one({"username": username}) is not None:
        flash('Username already exists.', 'error')
        return redirect(url_for('employees'))

    if password != confirm_password:
        flash('Passwords do not match.', 'error')
        return redirect(url_for('employees'))

    db.Users.insert_one({
        "username": username,
        "password": bcrypt.generate_password_hash(password).decode("utf-8"),
        "role": role,
        "branch_id": branch_id,
        "organization_id": ObjectId(organization_id),
        "active_status": True
    })

    flash('Employee added successfully!', 'success')
    return redirect(url_for('employees'))



@app.route('/edit_employee', methods=['POST'])
def edit_employee():
    employee_id = request.form.get('employee_id')
    username = request.form.get('username').strip()
    role = request.form.get('role').strip()
    branch_id = request.form.get('branch_id')

    employee = db.Users.find_one({"_id": ObjectId(employee_id)})
    if username != employee.get("username") and db.Users.find_one({"username": username}):
        flash('Username already exists.', 'error')
        return redirect(url_for('employees'))

    db.Users.update_one(
        {"_id": ObjectId(employee_id)},
        {"$set": {
            "username": username,
            "role": role,
            "branch_id": branch_id
        }}
    )
    flash('Employee updated successfully!', 'success')
    return redirect(url_for('employees'))


@app.route('/edit_employee_password', methods=['POST'])
def edit_employee_password():
    employee_id = request.form.get('employee_id')
    password = request.form.get('password').strip()
    confirm_password = request.form.get('confirm_password').strip()

    if password != confirm_password:
        flash('Passwords do not match.', 'error')
        return redirect(url_for('employees'))

    db.Users.update_one(
        {"_id": ObjectId(employee_id)},
        {"$set": {
            "password": bcrypt.generate_password_hash(password).decode("utf-8")
        }}
    )
    flash('Password updated successfully!', 'success')
    return redirect(url_for('employees'))


@app.route('/delete_employee', methods=['POST'])
def delete_employee():
    employee_id = request.form.get('employee_id')

    if len(list(db.Sales.find({"user_id": str(employee_id)}))) > 0 or len(list(db.Expenses.find({"user_id": str(employee_id)}))) > 0:
        flash('Cannot delete employee with associated sales or expenses records.', 'error')
        return redirect(url_for('employees'))

    db.Users.delete_one({"_id": ObjectId(employee_id)})
    flash('Employee deleted successfully!', 'success')
    return redirect(url_for('employees'))







@app.route('/reports')
def reports():
    user = db.Users.find_one({"_id": ObjectId(session.get("userid"))})
    organization = db.Organizations.find_one({"_id": ObjectId(user.get("organization_id"))})
    user['organization'] = organization.get('organization')
    selected_branch = session.get("branch_id")
    branch = session.get("branch")

    return render_template('reports.html', user=user, selected_branch=selected_branch, organization=organization, branch=branch)

@app.route('/performance')
def performance():
    user = db.Users.find_one({"_id": ObjectId(session.get("userid"))})
    organization = db.Organizations.find_one({"_id": ObjectId(user.get("organization_id"))})
    user['organization'] = organization.get('organization')
    selected_branch = session.get("branch_id")
    branch = session.get("branch")

    return render_template('performance.html', user=user, selected_branch=selected_branch, organization=organization, branch=branch)

@app.route('/stock_movement')
def stock_movement():
    user = db.Users.find_one({"_id": ObjectId(session.get("userid"))})
    organization = db.Organizations.find_one({"_id": ObjectId(user.get("organization_id"))})
    user['organization'] = organization.get('organization')
    selected_branch = session.get("branch_id")
    branch = session.get("branch")

    return render_template('stock_movement.html', user=user, selected_branch=selected_branch, organization=organization, branch=branch)
