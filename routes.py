from __init__ import app, db, bcrypt
from flask import render_template, request, flash, redirect, url_for, session, send_file
import pandas as pd
from io import BytesIO
import json, secrets, datetime
from bson.objectid import ObjectId
from collections import defaultdict
from datetime import timedelta
from collections import defaultdict
from utils import login_required
from reportlab.lib.pagesizes import A5, letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm




# authentication
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



@app.route("/logout")
@login_required
def logout():
    session.clear()
    flash("You have been logged out successfully!", "success")
    return redirect(url_for("login"))



# registration
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

        org = db.Organizations.find_one({"organization": form_info.get("organization").strip()})

        db.Users.insert_one({
            "username": form_info.get("username").strip(),
            "email": form_info.get("email"),
            "password": bcrypt.generate_password_hash(form_info["password"]).decode("utf-8"),
            "role": "Manager",
            "organization_id": org.get("_id"),
            "branch_ids": [],
            "active_status": True
        })
        
        flash("You have been registered successfully!", "success")
        return redirect(url_for("login"))



# branch selection
@app.route('/change_branch', methods=["POST"])
@login_required
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
@login_required
def profile():
    user = db.Users.find_one({"_id": ObjectId(session.get("userid"))})
    organization = db.Organizations.find_one({"_id": ObjectId(user.get("organization_id"))})
    user['organization'] = organization.get('organization')
    selected_branch = session.get("branch")

    return render_template('profile.html',
                           user=user,
                           selected_branch=selected_branch,
                           organization=organization,
                           now=datetime.datetime.now(),
                           organizations=list(db.Organizations.find())
                           )



@app.route('/edit_profile', methods=['POST'])
@login_required
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
@login_required
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
@login_required
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
@login_required
def delete_branch():
    branch_id = request.form.get('branch_id')
    organization_id = request.form.get('organization_id')

    if len(list(db.Users.find({"branch_id": branch_id}))) > 0:
        flash('Branch cannot be deleted because it has users.', 'error')
        return redirect(url_for('profile'))
    
    if len(list(db.Stock.find({"branch_id": branch_id}))) > 0:
        flash('Branch cannot be deleted because it has stock items.', 'error')
        return redirect(url_for('profile'))
    
    if len(list(db.Sales.find({"branch_id": branch_id}))) > 0:
        flash('Branch cannot be deleted because it has sales records.', 'error')
        return redirect(url_for('profile'))

    db.Organizations.update_one(
        {"_id": ObjectId(organization_id)},
        {"$pull": {"branches": {"_id": branch_id}}}
    )
    flash('Branch deleted successfully!', 'success')
    return redirect(url_for('profile'))


@app.route('/add_branch', methods=['POST'])
@login_required
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


# stock management
@app.route('/stock', methods=['GET'])
@login_required
def stock():
    user = db.Users.find_one({"_id": ObjectId(session.get("userid"))})
    organization = db.Organizations.find_one({"_id": ObjectId(user.get("organization_id"))})
    user['organization'] = organization.get('organization')
    selected_branch = session.get("branch")
    branch = session.get("branch")

    if selected_branch is None:
        stock = list(db.Stock.find({"organization_id": ObjectId(organization.get("_id"))}).sort("name", 1))
        stock_history = list(db.Stock_movement.find({"organization_id": ObjectId(organization.get("_id"))}).sort("date", -1))
        for item in stock:
            item['branch'] = next((b for b in organization.get("branches", []) if b.get("_id") == item.get("branch_id")), {}).get("branch")
        for item in stock_history:
            item['updater'] = db.Users.find_one({"_id": ObjectId(item.get("updater_id"))}).get("username")
    else:
        stock = list(db.Stock.find({ "organization_id": ObjectId(organization.get("_id")), "branch_id": branch.get("_id") }).sort("name", 1))
        stock_history = list(db.Stock_movement.find({"organization_id": ObjectId(organization.get("_id")), "branch_id": branch.get("_id")}).sort("date", -1))
        for item in stock:
            item['branch'] = next((b for b in organization.get("branches", []) if b.get("_id") == item.get("branch_id")), {}).get("branch")
        for item in stock_history:
            item['updater'] = db.Users.find_one({"_id": ObjectId(item.get("updater_id"))}).get("username")

    return render_template('stock.html',
                           user=user,
                           selected_branch=selected_branch,
                           organization=organization,
                           branch=branch,
                           stock=stock,
                           stock_history=stock_history,
                           now=datetime.datetime.now(),
                           organizations=list(db.Organizations.find())
                           )



@app.route('/add_item', methods=['POST'])
@login_required
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
        "quantity": 0,
    })
    flash('Item added successfully!', 'success')
    return redirect(url_for('stock'))



@app.route('/edit_item', methods=['POST'])
@login_required
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
@login_required
def update_stock():
    item_id = request.form.get('item_id')
    quantity = int(request.form.get('quantity'))
    unit_cost = int(request.form.get('unit_cost'))
    organization_id = request.form.get('organization_id')
    updater_id = request.form.get('user_id')
    branch_id = request.form.get('branch_id')
    date = datetime.datetime.strptime(request.form.get('date'), "%Y-%m-%d")

    db.Stock_movement.insert_one({
            "date": date,
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
            "quantity": item.get("quantity", 0) + quantity
        }}
    )   

    flash('Stock updated successfully!', 'success')
    return redirect(url_for('stock'))



@app.route('/delete_item', methods=['POST'])
@login_required
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
@login_required
def employees():
    user = db.Users.find_one({"_id": ObjectId(session.get("userid"))})
    organization = db.Organizations.find_one({"_id": ObjectId(user.get("organization_id"))})
    user['organization'] = organization.get('organization')
    selected_branch = session.get("branch")

    if selected_branch == None:
        employees = list(db.Users.find({"organization_id": ObjectId(user.get("organization_id"))}))
    else:
        employees = list(db.Users.find({"organization_id": ObjectId(user.get("organization_id")), "branch_id": selected_branch.get("_id")}))

    sales = list(db.Sales.find({"organization_id": ObjectId(user.get("organization_id"))}))
    expenses = list(db.Expenses.find({"organization_id": ObjectId(user.get("organization_id"))}))

    stock_items = list(db.Stock.find({"organization_id": ObjectId(user.get("organization_id"))}))

    for sale in sales:
        sale['type'] = 'Sale'
        sale['desc'] = []
        for item in sale.get("sale_items", []):
            item_name = next((stock_item.get("name") for stock_item in stock_items if str(stock_item.get("_id")) == str(item.get("item_id"))), "Unknown Item")
            sale['desc'].append(f'{item_name} ({item.get("quantity", 0)})')
        sale['desc'] = ", ".join(sale['desc'])
        sale['status'] = sale.get("payment_details", {}).get("status", "Unknown")
        sale['amount'] = sum(int(k["amount_paid"]) for k in sale.get("payment_details", {}).get("clearance_history", []))

        for expense in expenses:
            expense['type'] = 'Expense'
            expense['desc'] = expense.get("purpose", "")
            expense['authorizer'] = next((emp.get("username") for emp in employees if str(emp.get("_id")) == str(expense.get("authorized_by"))), "Unknown")

    transactions = sorted(sales + expenses, key=lambda x: x.get("date"), reverse=True)

    for e in employees:
        e['branch'] = next((item for item in organization.get("branches", []) if item["_id"] == e.get("branch_id")), {}).get("branch")

    return render_template('employees.html',
                           user=user,
                           selected_branch=selected_branch,
                           organization=organization,
                           employees=employees,
                           now=datetime.datetime.now(),
                           organizations=list(db.Organizations.find()),
                           transactions=transactions
                           )


@app.route('/add_employee', methods=['POST'])
@login_required
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
@login_required
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
@login_required
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
@login_required
def delete_employee():
    employee_id = request.form.get('employee_id')

    if len(list(db.Sales.find({"user_id": str(employee_id)}))) > 0 or len(list(db.Expenses.find({"user_id": str(employee_id)}))) > 0:
        flash('Cannot delete employee with associated sales or expenses records.', 'error')
        return redirect(url_for('employees'))

    db.Users.delete_one({"_id": ObjectId(employee_id)})
    flash('Employee deleted successfully!', 'success')
    return redirect(url_for('employees'))




# stock movement
@app.route('/stock_movement')
@login_required
def stock_movement():
    user = db.Users.find_one({"_id": ObjectId(session.get("userid"))})
    organization = db.Organizations.find_one({"_id": ObjectId(user.get("organization_id"))})
    user['organization'] = organization.get('organization')
    selected_branch = session.get("branch")
    branch = session.get("branch")

    if session.get("branch") is None:
        stock_history = list(db.Stock_movement.find({"organization_id": organization.get("_id")}).sort("date", -1))
        for movement in stock_history:
            movement["updater"] = db.Users.find_one({"_id": ObjectId(movement.get("updater_id"))}).get("username", "")
            movement["item"] = db.Stock.find_one({"_id": ObjectId(movement.get("item_id"))}).get("name", "")
            movement["branch"] = next((b for b in organization.get("branches", []) if b.get("_id") == movement.get("branch_id")), {}).get("branch", "")
    else:
        stock_history = list(db.Stock_movement.find({"organization_id": organization.get("_id"), "branch_id": branch.get("_id")}).sort("date", -1))
        for movement in stock_history:
            movement["updater"] = db.Users.find_one({"_id": ObjectId(movement.get("updater_id"))}).get("username", "")
            movement["item"] = db.Stock.find_one({"_id": ObjectId(movement.get("item_id"))}).get("name", "")
            movement["branch"] = next((b for b in organization.get("branches", []) if b.get("_id") == movement.get("branch_id")), {}).get("branch", "")

    return render_template('stock_movement.html',
                           user=user,
                           selected_branch=selected_branch,
                           organization=organization,
                           branch=branch,
                           stock_history=stock_history,
                           now=datetime.datetime.now(),
                           organizations=list(db.Organizations.find())
                           )


@app.route('/edit_stock_movement', methods=['POST'])
@login_required
def edit_stock_movement():
    movement_id = request.form.get('movement_id')
    item_id = request.form.get('item_id')
    new_quantity = int(request.form.get('quantity'))
    new_unit_cost = int(request.form.get('unit_cost'))
    date = datetime.datetime.strptime(request.form.get('date'), "%Y-%m-%d")

    item = db.Stock.find_one({"_id": ObjectId(item_id)})
    movement = db.Stock_movement.find_one({"_id": ObjectId(movement_id)})

    db.Stock_movement.update_one(
        {"_id": ObjectId(movement_id)},
        {"$set": {
            "quantity_updated": new_quantity,
            "unit_cost": new_unit_cost,
            "date": date
        }}
    )

    db.Stock.update_one(
        {"_id": ObjectId(item_id)},
        {"$set": {
            "quantity": item.get("quantity", 0) - movement.get("quantity_updated", 0) + new_quantity
        }}
    )

    flash('Stock movement updated.', 'success')
    return redirect(url_for('stock_movement'))


@app.route('/delete_stock_movement', methods=['POST'])
@login_required
def delete_stock_movement():
    movement_id = request.form.get('movement_id')
    item_id = request.form.get('item_id')

    movement = db.Stock_movement.find_one({"_id": ObjectId(movement_id)})
    item = db.Stock.find_one({"_id": ObjectId(item_id)})

    db.Stock_movement.delete_one({"_id": ObjectId(movement_id)})
    db.Stock.update_one(
        {"_id": ObjectId(item_id)},
        {"$inc": {"quantity": -1 * (movement.get("quantity_updated", 0))}}
    )

    flash('Stock movement deleted.', 'success')
    return redirect(url_for('stock_movement'))





# transactions (sales / expenses)
@app.route('/transactions')
@login_required
def transactions():
    user = db.Users.find_one({"_id": ObjectId(session.get("userid"))})
    organization = db.Organizations.find_one({"_id": ObjectId(user.get("organization_id"))})
    employees = list(db.Users.find({"organization_id": ObjectId(user.get("organization_id"))}))
    selected_branch = session.get("branch")
    user["organization"] = organization.get('organization')

    if selected_branch is None:
        sales = list(db.Sales.find({"organization_id": ObjectId(user.get("organization_id"))}).sort("date", -1))
        expenses = list(db.Expenses.find({"organization_id": ObjectId(user.get("organization_id"))}).sort("date", -1))
        stock_items = list(db.Stock.find({"organization_id": ObjectId(user.get("organization_id"))}).sort("name", 1))

    else:
        sales = list(db.Sales.find({"organization_id": ObjectId(user.get("organization_id")), "branch_id": selected_branch.get("_id")}).sort("date", -1))
        expenses = list(db.Expenses.find({"organization_id": ObjectId(user.get("organization_id")), "branch_id": selected_branch.get("_id")}).sort("date", -1))
        stock_items = list(db.Stock.find({"organization_id": ObjectId(user.get("organization_id")), "branch_id": selected_branch.get("_id")}).sort("name", 1))

    for sale in sales:
        sale["type"] = "Sale"
        sale["user_name"] = next((emp.get("username") for emp in employees if str(emp.get("_id")) == str(sale.get("user_id"))), "Unknown")
        sale["description"] = []
        for item in sale.get("sale_items", []):
            item_name = next((stock_item.get("name") for stock_item in stock_items if str(stock_item.get("_id")) == str(item.get("item_id"))), "Unknown Item")
            sale["description"].append(f'{item_name} ({item.get("quantity", 0)})')
        sale["description"] = ", ".join(sale["description"])
        sale["status"] = sale.get("payment_details", {}).get("status", "Unknown")
        sale["amount"] = sum(int(k["amount_paid"]) for k in sale.get("payment_details", {}).get("clearance_history", []))

    for expense in expenses:
        expense["type"] = "Expense"
        expense["user_name"] = next((emp.get("username") for emp in employees if str(emp.get("_id")) == str(expense.get("user_id"))), "Unknown")
        expense["description"] = expense.get("purpose", "")
        expense["authorizer"] = next((emp.get("username") for emp in employees if str(emp.get("_id")) == str(expense.get("authorized_by"))), "Unknown")

    transactions = sorted(sales + expenses, key=lambda x: x.get("date"), reverse=True)

    return render_template("transactions.html",
                           transactions=transactions,
                           user=user,
                           organization=organization,
                           employees=employees,
                           stock_items=stock_items,
                           selected_branch=selected_branch,
                           now=datetime.datetime.now(),
                           organizations=list(db.Organizations.find()))

@app.route('/new_sale', methods=['POST'])
@login_required
def new_sale():
    user_id = request.form.get('user_id')
    org_id = request.form.get('org_id')
    branch_id = request.form.get('branch_id')
    sale_items = request.form.get('sale_items')
    amount_paid = float(request.form.get('amount_paid', 0))
    client_name = request.form.get('client_name') or None
    client_contact = request.form.get('client_contact') or None

    sale_items = json.loads(sale_items)
    total = int(sum(float(i.get('quantity', 0)) * float(i.get('unit_price', 0)) for i in sale_items))

    print(total, amount_paid)

    db.Sales.insert_one({
        "organization_id":ObjectId(org_id),
        "user_id": ObjectId(user_id),
        "branch_id": branch_id,
        "date": datetime.datetime.now(),
        "sale_items": sale_items,
        "client_name": client_name,
        "client_contact": client_contact,
        "payment_details": {
            "status": "paid" if amount_paid >= total else "credit",
            "amount_left": total - amount_paid,
            "clearance_history": [{"date": datetime.datetime.now(), "amount_paid": amount_paid}]
        }
    })

    for item in sale_items:
        item_id = item.get('item_id')
        quantity = int(item.get('quantity', 0))
        db.Stock.update_one({"_id": ObjectId(item_id)}, {"$inc": {"quantity": -quantity}})

    flash('Sale recorded.', 'success')
    return redirect(url_for('transactions'))



@app.route('/edit_sale', methods=['POST'])
@login_required
def edit_sale():
    user_id = request.form.get('user_id')
    tx_id = request.form.get('tx_id')
    sale_items = request.form.get('sale_items')
    amount_paid = float(request.form.get('amount_paid', 0))
    client_name = request.form.get('client_name') or None
    client_contact = request.form.get('client_contact') or None

    sale_items = json.loads(sale_items)
    total = int(sum(float(i.get('quantity', 0)) * float(i.get('unit_price', 0)) for i in sale_items))

    old_tx = db.Sales.find_one({"_id": ObjectId(tx_id)})
    old_items = old_tx.get("sale_items", [])
    for old_item in old_items:
        old_item_id = old_item.get("item_id")
        old_quantity = int(old_item.get("quantity", 0))
        db.Stock.update_one({"_id": ObjectId(old_item_id)}, {"$inc": {"quantity": old_quantity}})

    for new_item in sale_items:
        new_item_id = new_item.get("item_id")
        new_quantity = int(new_item.get("quantity", 0))
        db.Stock.update_one({"_id": ObjectId(new_item_id)}, {"$inc": {"quantity": -new_quantity}})

    db.Sales.update_one({"_id": ObjectId(tx_id)}, {"$set": {
        "sale_items": sale_items,
        "client_name": client_name,
        "client_contact": client_contact,
        "payment_details": {
            "status": "paid" if amount_paid >= total else "credit",
            "amount_left": total - amount_paid,
            "clearance_history": [{"date": datetime.datetime.now(), "amount_paid": amount_paid}]
        }
    }})
    
    flash('Sale recorded.', 'success')
    return redirect(url_for('transactions'))




@app.route('/clear_credit', methods=['POST'])
@login_required
def clear_credit():
    user_id = request.form.get('user_id')
    tx_id = request.form.get('tx_id')
    amount_paid = int(request.form.get('amount', 0))

    db.Sales.update_one({"_id": ObjectId(tx_id)}, {"$push": {"payment_details.clearance_history": {"date": datetime.datetime.now(), "amount_paid": amount_paid}}})

    transaction = db.Sales.find_one({"_id": ObjectId(tx_id)})
    total_paid = sum(entry.get("amount_paid", 0) for entry in transaction.get("payment_details", {}).get("clearance_history", []))
    amount_left = int(sum(float(item.get("quantity", 0)) * float(item.get("unit_price", 0)) for item in transaction.get("sale_items", []))) - total_paid

    db.Sales.update_one({"_id": ObjectId(tx_id)}, {"$set": {
        "payment_details.status": "paid" if amount_left <= 0 else "credit",
        "payment_details.amount_left": amount_left
    }})

    flash('Credit cleared.', 'success')
    return redirect(url_for('transactions'))



@app.route('/print_receipt', methods=['POST'])
@login_required
def print_receipt():
    date = request.form.get('date')
    organization_id = request.form.get('organization_id')
    client_name = request.form.get('client_name')
    client_contact = request.form.get('client_contact')
    seller = request.form.get('seller')
    branch_id = request.form.get('branch_id')
    tx_id = request.form.get('tx_id')

    organization = db.Organizations.find_one({"_id": ObjectId(organization_id)})
    branch = next((b for b in organization.get("branches", []) if str(b.get("_id")) == str(branch_id)), None)
    transaction = db.Sales.find_one({"_id": ObjectId(tx_id)})
    sale_items = transaction.get("sale_items", [])
    
    stock_items = list(db.Stock.find({"organization_id": ObjectId(organization_id)}))

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    w, h = letter
    y = h - 20*mm

    def line(txt, inc=6):
        nonlocal y
        c.drawString(15*mm, y, txt)
        y -= inc*mm

    #document set up and printing
    c.setFont("Helvetica", 11)
    line(str(organization.get("organization", "")).upper() + " - RECEIPT")
    line("Branch / Location: " + (branch.get('branch', '') if branch else ''))

    c.line(15*mm, y, w - 15*mm, y)
    y -= 6*mm
    c.setFont("Helvetica-Oblique", 11)
    line("Date:    " + date)

    c.setFont("Helvetica", 11)
    c.setDash(3, 2)
    c.line(15*mm, y, w - 15*mm, y)
    y -= 6*mm

    for k in sale_items:
        item_name = next((stock_item.get("name") for stock_item in stock_items if str(stock_item.get("_id")) == str(k.get("item_id"))), "Unknown Item")
        item_str = f"Item: {item_name}        Quantity: {k.get('quantity', 'N/A')}        Unit Price: {'{:,}'.format(int(k.get('unit_price', 0)))}"
        line(item_str)
        y -= 4*mm

    c.line(15*mm, y, w - 15*mm, y)
    y -= 6*mm
    line("Payment Details:")
    for payment in transaction.get("payment_details", {}).get("clearance_history", []):
        line("    Date:    " + datetime.datetime.strftime(payment.get("date", ""), "%d %b %Y") + ",    Amount Paid:    " + "{:,}".format(payment.get("amount_paid", 0)))
    
    c.line(15*mm, y, w - 15*mm, y)
    y -= 6*mm
    line("Amount Left:    " + str(transaction.get("payment_details", {}).get("amount_left", 0)))

    c.line(15*mm, y, w - 15*mm, y)
    y -= 6*mm
    line("Client:    " + (client_name if client_name else "N/A"))
    line("Contact:    " + (client_contact if client_contact else "N/A"))
    c.line(15*mm, y, w - 15*mm, y)
    y -= 6*mm
    line("Seller:    " + seller if seller else "N/A")

    c.setFont("Helvetica-Oblique", 11)
    c.line(15*mm, y, w - 15*mm, y)
    y -= 6*mm
    line("Receipt ID:    " + str(tx_id))
    # line("Organization ID    :" + str(organization_id))

    c.setDash()
    c.line(15*mm, y, w - 15*mm, y)
    y -= 6*mm
    c.setFont("Helvetica-Oblique", 10)
    line("Thank you for your business!, come again.")

    c.showPage()
    c.save()
    buf.seek(0)

    return send_file(
        buf,
        as_attachment=False,
        download_name=f"receipt-{tx_id}.pdf",
        mimetype="application/pdf"
    )


@app.route('/new_expense', methods=['POST'])
@login_required
def new_expense():
    user_id = request.form.get('user_id')
    org_id = request.form.get('org_id')
    branch_id = request.form.get('branch_id')
    purpose = request.form.get('purpose').strip()
    amount = float(request.form.get('amount', 0))
    authorized_by = request.form.get('authorized_by') or None

    db.Expenses.insert_one({
        "user_id": ObjectId(user_id),
        "organization_id": ObjectId(org_id),
        "branch_id": branch_id,
        "purpose": purpose,
        "amount": amount,
        "authorized_by": authorized_by,
        "date": datetime.datetime.now()
    })

    flash('Expense recorded.', 'success')
    return redirect(url_for('transactions'))


@app.route('/edit_expense', methods=['POST'])
@login_required
def edit_expense():

    tx_id = request.form.get('tx_id')
    purpose = request.form.get('purpose').strip()
    amount = request.form.get('amount', 0)
    authorized_by = request.form.get('authorized_by') or None

    db.Expenses.update_one({"_id": ObjectId(tx_id)}, {"$set": {
        "purpose": purpose,
        "amount": float(amount),
        "authorized_by": authorized_by
    }})

    flash('Expense updated.', 'success')
    return redirect(url_for('transactions'))

@app.route('/delete_transaction', methods=['POST'])
def delete_transaction():
    tx_id = request.form.get('tx_id')
    tx_type = request.form.get('tx_type')

    if tx_type == "Sale":
        tx = db.Sales.find_one({"_id": ObjectId(tx_id)})
        for item in tx.get("sale_items", []):
            db.Stock.update_one({"_id": ObjectId(item.get("item_id"))}, {"$inc": {"quantity": item.get("quantity", 0)}})
        db.Sales.delete_one({"_id": ObjectId(tx_id)})
    else:
        db.Expenses.delete_one({"_id": ObjectId(tx_id)})

    flash('Transaction deleted.', 'success')
    return redirect(url_for('transactions'))


# performance
@app.route('/performance')
@login_required
def performance():
    user = db.Users.find_one({"_id": ObjectId(session.get("userid"))})
    organization = db.Organizations.find_one({"_id": ObjectId(user.get("organization_id"))})
    user['organization'] = organization.get('organization')
    selected_branch = session.get("branch")

    if selected_branch is None:
        sales = db.Sales.find({"organization_id": organization.get("_id")})
        expenses = db.Expenses.find({"organization_id": organization.get("_id")})
        stock_movement = db.Stock_movement.find({"organization_id": organization.get("_id")})
    else:
        sales = db.Sales.find({"organization_id": organization.get("_id"), "branch_id": selected_branch.get("_id")})
        expenses = db.Expenses.find({"organization_id": organization.get("_id"), "branch_id": selected_branch.get("_id")})
        stock_movement = db.Stock_movement.find({"organization_id": organization.get("_id"), "branch_id": selected_branch.get("_id")})

    
    monthly_sales = defaultdict(float)
    for sale in sales:
        month = sale.get("date").strftime("%B-%Y")
        for sale_item in sale.get("sale_items", []):
            monthly_sales[month] += int(float(sale_item.get("quantity", 0)) * float(sale_item.get("unit_price", 0)))

    monthly_expenses = defaultdict(float)
    for expense in expenses:
        month = expense.get("date").strftime("%B-%Y")
        monthly_expenses[month] += expense.get("amount", 0)

    monthly_stock_cost = defaultdict(float)
    for stock in stock_movement:
        month = stock.get("date").strftime("%B-%Y")
        monthly_stock_cost[month] += stock.get("quantity_updated", 0) * stock.get("unit_cost", 0)

    all_months = sorted(set(monthly_sales.keys()) | set(monthly_expenses.keys()) | set(monthly_stock_cost.keys()))
    
    performance_data = []
    for month in all_months:
        sales_total = monthly_sales.get(month, 0)
        expenses_total = monthly_expenses.get(month, 0)
        stock_cost_total = monthly_stock_cost.get(month, 0)
        profit = sales_total - expenses_total - stock_cost_total
        profit_margin = (profit / sales_total)*100 if sales_total != 0 else 0
        performance_data.append({
            "month": month,
            "sales": sales_total,
            "expenses": expenses_total,
            "stock_cost": stock_cost_total,
            "profit": profit,
            "profit_margin": profit_margin
        })

    return render_template('performance.html',
                           user=user,
                           selected_branch=selected_branch,
                           organization=organization,
                           performance_data=performance_data,
                           now=datetime.datetime.now(),
                           organizations=list(db.Organizations.find())
                       )



# reports
@app.route('/reports')
@login_required
def reports():
    user = db.Users.find_one({"_id": ObjectId(session.get("userid"))})
    organization = db.Organizations.find_one({"_id": ObjectId(user.get("organization_id"))})
    user['organization'] = organization.get('organization')
    selected_branch = session.get("branch")

    return render_template('reports.html',
                           user=user,
                           selected_branch=selected_branch,
                           organization=organization,
                           now=datetime.datetime.now(),
                            organizations=list(db.Organizations.find())
                           )

@app.route('/generate_report', methods=['POST'])
@login_required
def generate_report():
    user = db.Users.find_one({"_id": ObjectId(session.get("userid"))})
    start_date = request.form.get('start_date')
    end_date = request.form.get('end_date')
    data = request.form.get('data')
    branch_id = request.form.get('branch_id')


    start_date = datetime.datetime.strptime(start_date, "%Y-%m-%d").date()
    end_date = datetime.datetime.strptime(end_date, "%Y-%m-%d").date()

    if start_date > end_date:
        flash('Invalid date range. Please try again.', 'error')
        return redirect(url_for('reports'))


    if branch_id == "all":
        branch_name = "all"
    else:
        org_info = db.Organizations.find_one({"_id": ObjectId(user.get("organization_id"))})
        branch_name = "unknown"
        for branch in org_info.get("branches", []):
            if branch.get("_id") == branch_id:
                branch_name = branch.get("branch")
                break

    if data == "sales":
        if branch_id == "all":
            sales = list(db.Sales.find({"organization_id": ObjectId(user.get("organization_id"))}))
        else:
            sales = list(db.Sales.find({"organization_id": ObjectId(user.get("organization_id")), "branch_id": branch_id}))
        sales = [s for s in sales if start_date <= s.get("date").date() <= end_date]
        
        required_data = []
        users = list(db.Users.find({"organization_id": ObjectId(user.get("organization_id"))}))
        stock_items = list(db.Stock.find({"organization_id": ObjectId(user.get("organization_id"))}))
        
        for i in sales:
            items = []
            for k in i.get("sale_items", []):
                item_name = next((s["name"] for s in stock_items if str(s["_id"]) == str(k["item_id"])), "Unknown")
                items.append(f'{item_name} ({k.get("quantity", 0)} x {k.get("unit_price", 0)})')
            items = ", ".join(items)
            required_data.append({
                "date": i.get("date").date().strftime("%d %B %Y"),
                "sales person": next((u["username"] for u in users if str(u["_id"]) == str(i["user_id"])), "Unknown"),
                "products/services": items,
                "amount paid": sum(float(k["amount_paid"]) for k in  i.get("payment_details", {}).get("clearance_history", [])),
                "status": i.get("payment_details", {}).get("status"),
                "client name": i.get("client_name"),
                "client contact": i.get("client_contact")
            })

        df = pd.DataFrame(required_data)
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Sheet1")
        output.seek(0)
        return send_file(
            output,
            as_attachment=True,
            download_name=f"{branch_name}-sales-{start_date.strftime('%d-%b-%Y')}--{end_date.strftime('%d-%b-%Y')}.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    

    if data == "expenses":
        if branch_id == "all":
            expenses = list(db.Expenses.find({"organization_id": ObjectId(user.get("organization_id"))}))
        else:
            expenses = list(db.Expenses.find({"organization_id": ObjectId(user.get("organization_id")), "branch_id": branch_id}))
        expenses = [e for e in expenses if start_date <= e.get("date").date() <= end_date]

        required_data = []
        users = list(db.Users.find({"organization_id": ObjectId(user.get("organization_id"))}))
        for i in expenses:
            required_data.append({
                "date": i.get("date").date().strftime("%d %B %Y"),
                "spend by": next((u["username"] for u in users if str(u["_id"]) == str(i["user_id"])), "Unknown"),
                "expense": i.get("purpose"),
                "amount": i.get("amount")
            })

        df = pd.DataFrame(required_data)
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Sheet1")
        output.seek(0)
        return send_file(
            output,
            as_attachment=True,
            download_name=f"{branch_name}-expenses-{start_date.strftime('%d-%b-%Y')}--{end_date.strftime('%d-%b-%Y')}.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    

    if data == "stock_movement":
        if branch_id == "all":
            stock_movements = list(db.Stock_movement.find({"organization_id": ObjectId(user.get("organization_id"))}))
        else:
            stock_movements = list(db.Stock_movement.find({"organization_id": ObjectId(user.get("organization_id")), "branch_id": branch_id}))
        stock_movements = [sm for sm in stock_movements if start_date <= sm.get("date").date() <= end_date]

        required_data = []
        users = list(db.Users.find({"organization_id": ObjectId(user.get("organization_id"))}))
        stock_items = list(db.Stock.find({"organization_id": ObjectId(user.get("organization_id"))}))
        for i in stock_movements:
            required_data.append({
                "date": i.get("date").date().strftime("%d %B %Y"),
                "updated by": next((u["username"] for u in users if str(u["_id"]) == str(i["updater_id"])), "Unknown"),
                "item": next((si["name"] for si in stock_items if str(si["_id"]) == str(i["item_id"])), "Unknown"),
                "quantity": i.get("quantity_updated"),
                "unit cost": i.get("unit_cost"),
                "amount": float(i.get("quantity_updated"))*float(i.get("unit_cost")),
            })

        df = pd.DataFrame(required_data)
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Sheet1")
        output.seek(0)
        return send_file(
            output,
            as_attachment=True,
            download_name=f"{branch_name}-stock-movement-{start_date.strftime('%d-%b-%Y')}--{end_date.strftime('%d-%b-%Y')}.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    flash('Report generation failed. Please try again.', 'error')
    return redirect(url_for('reports'))

@app.route('/change_organization', methods=['POST'])
@login_required
def change_organization():
    organization_id = request.form.get('organization_id')
    user = db.Users.find_one({"_id": ObjectId(session.get("userid"))})
    if user.get("role") == "Admin":
        session.pop("branch", None)
        db.Users.update_one({"_id": ObjectId(session.get("userid"))}, {"$set": {"organization_id": ObjectId(organization_id)}})
        flash('Organization changed successfully.', 'success')
    else:
        flash('Failed to change organization. Please try again.', 'error')
    return redirect(url_for('transactions'))