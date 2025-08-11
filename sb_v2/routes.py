from sb_v2 import app, db, bcrypt
from flask import render_template, request, flash, redirect, url_for, session
import json, secrets, datetime
from bson.objectid import ObjectId
from collections import defaultdict


@app.route('/home', methods=["GET", "POST"])
def home():
    selected_branch_id = ""
    user = db.Users.find_one({"_id": ObjectId(session.get("userid"))})
    user["_id"] = str(user["_id"])
    organization = db.Organizations.find_one({"_id": user["organization_id"]})
    employees = list(db.Users.find({"organization_id": user["organization_id"]}))
    stock_items = list(db.Stock.find({"organization_id": user["organization_id"]}).sort("quantity", -1))
    stock_history = list(db.Stock_movement.find({"organization_id": user["organization_id"]}).sort("date", -1))

    if user["role"] == "Manager":
        if request.method == "GET":
            selected_branch_id = session.get('selected_branch_id', "")
            if selected_branch_id == "" or selected_branch_id == None:
                sales = list(db.Sales.find({"organization_id": ObjectId(user["organization_id"])}).sort("date", -1))
                expenses = list(db.Expenses.find({"organization_id": ObjectId(user["organization_id"])}).sort("date", -1))
                stock_history = list(db.Stock_movement.find({"organization_id": user["organization_id"]}).sort("date", -1))
                stock_items = list(db.Stock.find({"organization_id": user["organization_id"]}).sort("quantity", -1))

            else:
                sales = list(db.Sales.find({"organization_id": ObjectId(user["organization_id"]), "branch_id": selected_branch_id}).sort("date", -1))
                expenses = list(db.Expenses.find({"organization_id": ObjectId(user["organization_id"]), "branch_id": selected_branch_id}).sort("date", -1))
                stock_history = list(db.Stock_movement.find({"organization_id": user["organization_id"], "branch_id": selected_branch_id}).sort("date", -1))
                stock_items = list(db.Stock.find({"organization_id": user["organization_id"], "branch_id": selected_branch_id}).sort("quantity", -1))


        elif request.method == "POST":
            selected_branch_id = request.form["branch_id"]
            session['selected_branch_id'] = selected_branch_id
            return redirect(url_for('home'))

    if user["role"] == "Branch Manager":
        selected_branch_id = ""
        sales = list(db.Sales.find({"organization_id": ObjectId(user["organization_id"]), "branch_id": user["branch_ids"][0]}).sort("date", -1))
        expenses = list(db.Expenses.find({"organization_id": ObjectId(user["organization_id"]), "branch_id": user["branch_ids"][0]}).sort("date", -1))
        stock_history = list(db.Stock_movement.find({"organization_id": user["organization_id"], "branch_id": user["branch_ids"][0]}).sort("date", -1))
        stock_items = list(db.Stock.find({"organization_id": user["organization_id"], "branch_id": user["branch_ids"][0]}).sort("quantity", -1))


    
    if user["role"] == "Sales person": 
        selected_branch_id = ""
        sales = list(db.Sales.find({"organization_id": ObjectId(user["organization_id"]), "user_id": str(user["_id"])}).sort("date", -1))
        expenses = list(db.Expenses.find({"organization_id": ObjectId(user["organization_id"]), "user_id": str(user["_id"])}).sort("date", -1))
        stock_items = list(db.Stock.find({"organization_id": user["organization_id"], "branch_id": user["branch_ids"][0]}).sort("quantity", -1))
        stock_history = list(db.Stock_movement.find({"organization_id": user["organization_id"], "branch_id": user["branch_ids"][0]}).sort("date", -1))



    
    # adding necessary info on transactions
    for i in sales:
        i["type"] = "Sale"
        i["user_name"] = db.Users.find_one({"_id": ObjectId(i["user_id"])})["username"]
        i["description"] = db.Stock.find_one({"_id": ObjectId(i["item_id"])})["name"]
        i["status"] = i["payment_details"]["status"]
        i["amount"] = sum(float(k["amount_paid"]) for k in  i["payment_details"]["clearance_history"])
    for i in expenses:
        i["type"] = "Expense"
        i["user_name"] = db.Users.find_one({"_id": ObjectId(i["user_id"])})["username"]
        i["description"] = i["purpose"]
        i["quantity"] = "-"
        i["status"] = "-"
        i["authorizer"] = db.Users.find_one({"_id": ObjectId(i["authorized_by"])})["username"] if db.Users.find_one({"_id": ObjectId(i["authorized_by"])}) != None else None

    # getting monthly sales/revenue info
    monthly_sales = defaultdict(float)
    for sale in sales:
        # Getting month as YYYY-MM string
        month = sale["date"].strftime("%B-%Y")
        revenue = float(sale["quantity"]) * float(sale["unit_price"])
        monthly_sales[month] += revenue
    monthly_sales_list = [{"month": month, "total_sales_revenue": total}for month, total in sorted(monthly_sales.items())]

    # getting monthly (normal) expense info
    monthly_expenses = defaultdict(float)
    for expense in expenses:
        month = expense["date"].strftime("%B-%Y")
        spent_amount = float(expense["amount"])
        monthly_expenses[month] += spent_amount
    # monthly_expenses_list = [{"month": month, "total_expenses": total} for month, total in sorted(monthly_expenses.items())]
    
    # getting monthly stocking expenses info
    monthly_stock_expenses = defaultdict(float)
    for stock_expense in stock_history:
        month = stock_expense["date"].strftime("%B-%Y")
        stocking_expense = float(stock_expense["unit_cost"]) * float(stock_expense["quantity_updated"])
        monthly_stock_expenses[month] += stocking_expense
    # monthly_stocking_expenses_list = [{"month": month, "total_expenses": total} for month, total in sorted(monthly_stock_expenses.items())]

    # summing up expenses
    all_months = set(monthly_expenses) | set(monthly_stock_expenses)
    merged_expenses = [{"month": month, "total_expenses": monthly_expenses.get(month, 0) + monthly_stock_expenses.get(month, 0)} for month in sorted(all_months)]

    # getting monthly profit
    all_months_1 = set(monthly_sales) | set(monthly_expenses) | set(monthly_stock_expenses)
    monthly_profit = [{"month": month, "profit": monthly_sales.get(month, 0) - monthly_expenses.get(month, 0) - monthly_stock_expenses.get(month, 0)} for month in sorted(all_months_1)]
        
    transactions = sales + expenses    
    
    # adding information to stock history
    for m in stock_history:
        m["date"] = m["date"].strftime("%B %d, %Y")
        m["updater"] = db.Users.find_one({"_id": m["updater_id"]})["username"]
        m["quantity"] = m["quantity_updated"]
    
    # adding information to stock items
    for k in stock_items:
        for j in list(organization["branches"]):
            if str(k["branch_id"]) == str(j["_id"]):
                k["branch"] = j["branch"]
    
    # adding information to employees
    for i in employees:
        branch_objects = []
        for j in i["branch_ids"]:
            for m in organization["branches"]:
                if m["_id"] == j:
                    branch_objects.append(m)
        i["branches"] = branch_objects    

    # adding branch information to user object
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
                           selected_branch_id = selected_branch_id,
                           employees = list(employees),
                           stock_items = stock_items,
                           stock_history = stock_history,
                           transactions = sorted(transactions, key=lambda t: t["date"], reverse=True),
                           now=datetime.datetime.now(),
                           monthly_sales_list = monthly_sales_list,
                           monthly_expenses_list = merged_expenses,
                           monthly_profit = monthly_profit)

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
        if user == None:
            flash("Account doesnt exist, check user name!", "error")
            return redirect(url_for("login"))
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
        if db.Users.find_one({"email": form_info["email"]}) is None or form_info["email"]is "":
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
        print("reached here")
        if db.Users.find_one({"email": form_info["email"]}) is None or form_info.get("email") == "":
            db.Users.update_one({"_id": ObjectId(form_info["employee_id"])}, {
                "$set": {"email": form_info["email"]}
            })
        else:
            flash("Email Already Taken, Use Another")
    
    # updating role
    if db.Users.find_one({"_id": ObjectId(session.get("userid"))})["role"] == "Manager":
        db.Users.update_one({"_id": ObjectId(form_info["employee_id"])}, {
                "$set": {"role": form_info.get("role")}
            })

        # updating branch id
        db.Users.update_one({"_id": ObjectId(form_info["employee_id"])}, {
                "$set": {"branch_ids": [form_info.get("branch_id")]}
            })    
    return redirect(url_for("home"))


@app.route("/deactivate_employee)", methods=['POST'])
def deactivate_employee():
    form_info = request.form
    db.Users.update_one({"_id": ObjectId(form_info["employee_id"])}, {
            "$set": {"active_status": False}
        })
    flash("employee deactivated successfully", "success")
    return redirect(url_for("home"))

@app.route("/activate_employee)", methods=['POST'])
def activate_employee():
    form_info = request.form
    db.Users.update_one({"_id": ObjectId(form_info["employee_id"])}, {
            "$set": {"active_status": True}
        })
    flash("employee activated successfully", "success")
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
    if user["role"] == "Manager":
        db.Stock.insert_one({
            "name": form_info["name"],
            "quantity": 0,
            "price": 0,
            "branch_id": form_info["branch_id"],
            "organization_id": user["organization_id"]
        })
        flash("Item added successfully!", "success")
        return redirect(url_for("home"))
    if user["role"] == "Branch Manager":
        db.Stock.insert_one({
            "name": form_info["name"],
            "quantity": 0,
            "price": 0,
            "branch_id": user["branch_ids"][0],
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
            "$set": {"name": form_info["name"], "price": float(form_info["price"]), "branch_id": form_info["branch_id"]}
        })
    elif user["role"] == "Branch Manager":
        db.Stock.update_one({"_id": ObjectId(form_info["item_id"])}, {
            "$set": {"name": form_info["name"]}
        })
    flash("stock info updated successfully", "success")
    return redirect(url_for("home"))


@app.route("/update_stock_quantity)", methods=['POST'])
def update_stock_quantity():
    form_info = request.form
    user = db.Users.find_one({"_id": ObjectId(session.get("userid"))})
    item = db.Stock.find_one({"_id": ObjectId(form_info["item_id"])})
    if user["role"] == "Manager" or user["role"] == "Branch Manager":
        db.Stock.update_one({"_id": ObjectId(form_info["item_id"])}, {
            "$inc": {"quantity": int(form_info["quantity"])}
        })
        
        db.Stock_movement.insert_one({
            "date": datetime.datetime.now(),
            "organization_id": item["organization_id"],
            "branch_id": item["branch_id"],
            "updater_id": user["_id"],
            "item_id": form_info["item_id"],
            "quantity_updated": int(form_info["quantity"]),
            "unit_cost": float(form_info["unit_cost"])
        })
        flash("Quantity updated successfully!", "success")
        return redirect(url_for("home"))
    else:
        flash("Sales Personnel cannot update stock", "error")
        return redirect(url_for("home"))


@app.route("/new_sale)", methods=['POST'])
def new_sale():
    form_info = request.form
    user = db.Users.find_one({"_id": ObjectId(session.get("userid"))})
    item = db.Stock.find_one({"_id": ObjectId(form_info["item_id"])})
    db.Sales.insert_one({
        "organization_id": user["organization_id"],
        "branch_id": form_info["branch_id"] if user["role"] == "Manager" else user["branch_ids"][0],
        "user_id": form_info["user_id"],
        "item_id": form_info["item_id"],
        "date": datetime.datetime.now(),
        "quantity": int(form_info["quantity"]),
        "unit_price": float(form_info["unit_price"]),
        "client_name": form_info["client_name"],
        "client_contact": form_info["client_contact"],
        "payment_details": {
            "status": "paid" if float(form_info["amount_paid"]) >= float(form_info["unit_price"])*int(form_info["quantity"]) else "credit",
            "amount_left": float(form_info["unit_price"])*int(form_info["quantity"]) - float(form_info["amount_paid"]),
            "clearance_history": [{
                "date": datetime.datetime.now(),
                "amount_paid": float(form_info["amount_paid"])
            }]
        }
    })
    db.Stock.update_one({"_id": ObjectId(form_info["item_id"])}, {
        "$inc": {"quantity": -1*int(form_info["quantity"])}
    })
    flash("sale record uploaded successfully", "success")
    return redirect(url_for("home"))


@app.route("/new_expense)", methods=['POST'])
def new_expense():
    form_info = request.form
    user = db.Users.find_one({"_id": ObjectId(session.get("userid"))})
    db.Expenses.insert_one({
        "organization_id": user["organization_id"],
        "branch_id": form_info["branch_id"] if user["role"] == "Manager" else user["branch_ids"][0],
        "user_id": form_info["user_id"],
        "authorized_by": form_info.get("authorized_by"),
        "purpose": form_info["purpose"],
        "amount": float(form_info["amount"]),
        "date": datetime.datetime.now()
    })
    flash("expense record uploaded successfully", "success")
    return redirect(url_for("home"))


@app.route("/edit_sale)", methods=['POST'])
def edit_sale():
    form_info = request.form
    user = db.Users.find_one({"_id": ObjectId(session.get("userid"))})
    item = db.Stock.find_one({"_id": ObjectId(form_info["item_id"])})
    transaction = db.Sales.find_one({"_id": ObjectId(form_info["transaction_id"])})

    #updating transaction
    db.Sales.update_one({"_id": ObjectId(form_info["transaction_id"])}, {
        "$set": {
        "item_id": form_info["item_id"],
        "quantity": int(form_info["quantity"]),
        "unit_price": float(form_info["unit_price"]),
        "client_name": form_info["client_name"],
        "client_contact": form_info["client_contact"],
        "payment_details": {
            "status": "paid" if float(form_info["amount_paid"]) >= float(form_info["unit_price"])*int(form_info["quantity"]) else "credit",
            "amount_left": float(form_info["unit_price"])*int(form_info["quantity"]) - float(form_info["amount_paid"]),
            "clearance_history": [{
                "date": datetime.datetime.now(),
                "amount_paid": float(form_info["amount_paid"])
            }]
        }
    }
    })

    #updating stock
    if str(item["_id"]) == str(transaction["item_id"]):
        db.Stock.update_one({"_id": ObjectId(form_info["item_id"])}, {
            "$inc": {"quantity": -1*int(form_info["quantity"]) + int(transaction["quantity"])}
        })
    else:
        db.Stock.update_one({"_id": ObjectId(transaction["item_id"])}, {
            "$inc": {"quantity": int(transaction["quantity"])}
        })
        db.Stock.update_one({"_id": ObjectId(form_info["item_id"])}, {
            "$inc": {"quantity": -1*int(form_info["quantity"])}
        })
    flash("sale record update successful", "success")
    return redirect(url_for("home"))


@app.route("/edit_expense)", methods=['POST'])
def edit_expense():
    form_info = request.form
    user = db.Users.find_one({"_id": ObjectId(session.get("userid"))})
    transaction = db.Expenses.find_one({"_id": ObjectId(form_info["transaction_id"])})

    db.Expenses.update_one({"_id": ObjectId(form_info["transaction_id"])}, {
        "$set": {
        "authorized_by": form_info.get("authorized_by"),
        "purpose": form_info["purpose"],
        "amount": float(form_info["amount"]),
    }
    })
    flash("expense record update successsful", "success")
    return redirect(url_for("home"))


@app.route("/clear_credit)", methods=['POST'])
def clear_credit():
    form_info = request.form
    # user = db.Users.find_one({"_id": ObjectId(session.get("userid"))})
    transaction = db.Sales.find_one({"_id": ObjectId(form_info["transaction_id"])})
    db.Sales.update_one({"_id": ObjectId(form_info["transaction_id"])},
        {
            "$push": {
                "payment_details.clearance_history": {
                    "date": datetime.datetime.now(),
                    "amount_paid": float(form_info["amount"])
                }
            }
        }
    )

    #updating clearance history
    transaction = db.Sales.find_one({"_id": ObjectId(form_info["transaction_id"])})
    total_paid = sum(float(k["amount_paid"]) for k in transaction["payment_details"]["clearance_history"])
    amount_left = float(transaction["quantity"]) * float(transaction["unit_price"]) - total_paid
    
    db.Sales.update_one({"_id": ObjectId(form_info["transaction_id"])}, {
                "$set": {
            "payment_details.amount_left": amount_left
        }
    })

    #updating payment status
    db.Sales.update_one({"_id": ObjectId(form_info["transaction_id"])}, {
        "$set": {
            "payment_details.status": "paid" if amount_left <= 0 else "credit"
        }
    })
    
    flash("clearance update successful", "success")
    return redirect(url_for("home"))