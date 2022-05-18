import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    total_share = 0
    cash = None
    price = []

    portfolio = db.execute("SELECT users_id, symbol, quantity FROM portfolio WHERE users_id = ?", session["user_id"])

    # make a list of dict of lookup price & name accordingly AND appended in each row of portfolio
    for row in portfolio:
        l_result = lookup(row["symbol"])
        d = {"name": l_result["name"], "price": usd(l_result["price"]), "total": usd(
            l_result["price"]*row["quantity"]), "intotalprice": l_result["price"]*row["quantity"]}
        row.update(d)

    c_sql = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
    cash = c_sql[0]["cash"]

    for i in range(len(portfolio)):
        total_share = total_share + (portfolio[i]["intotalprice"])

    total_share = total_share + cash

    # "Show portfolio of stocks"
    return render_template("index.html", portfolio=portfolio, cash=usd(cash), total_val=usd(total_share))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    # check method of input
    if request.method == "POST":

        # check if symbol empty
        if not request.form.get("symbol"):
            return apology("must provide stock symbol")

        # print(type(request.form.get("quantity")))
        # check if quantity empty
        if not request.form.get("shares"):
            return apology("must provide no. of shares")

        # Store symbol & quantity
        symb = request.form.get("symbol").upper()
        try:
            qnt = float(request.form.get("shares"))
        except:
            return apology("must provide no. of shares")

        # check if quantity non negative or zero
        if qnt <= 0 or not qnt % 1 == 0:
            return apology("must provide no. of shares")

        # check if symbol EXIST ACTUALLY
        look_result = lookup(symb)

        if look_result is None:
            return apology("this stock symbol doesn't exist")

        # check if CASH AVAILABLE
        cash = db.execute("SELECT cash FROM users WHERE id = ?;", session["user_id"])

        if cash[0]['cash'] < look_result["price"] * qnt:
            return apology("Cash available is not enough")

        db.execute("INSERT INTO history (users_id, symbol, transactionType, marketPrice, quantity) VALUES (?, ?, ?, ?, ?)",
                   session["user_id"], symb, "buy", look_result["price"], qnt)

        db.execute("UPDATE users SET cash = ? WHERE id = ?", cash[0]['cash'] - (look_result["price"] * qnt), session["user_id"])

        look_sym = db.execute("SELECT * FROM portfolio WHERE users_id = ? AND symbol = ?", session["user_id"], symb)

        # check if symbol inside portfolio or not
        if len(look_sym) == 0:
            db.execute("INSERT INTO portfolio (users_id, symbol, quantity) VALUES (?, ?, ?)", session["user_id"], symb, qnt)
        else:
            db.execute("UPDATE portfolio SET quantity = ? WHERE users_id = ? AND symbol = ? ",
                       look_sym[0]["quantity"] + qnt, session["user_id"], symb)

        return redirect("/")

    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():

    # load history table
    history = db.execute(
        "SELECT transactionType, marketPrice, symbol, quantity, DATE(dateTime) AS date, TIME(dateTime) AS time FROM history WHERE users_id = ?",
        session["user_id"])

    # "Show history of transactions"
    return render_template("history.html", history=history)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    if request.method == "POST":

        if not request.form.get("symbol"):
            return apology("must provide stock symbol")

        look_result = lookup(request.form.get("symbol").upper())

        if look_result is None:
            return apology("this stock symbol doesn't exist")

        return render_template('quoted.html', result=look_result, price=usd(look_result["price"]))

    # Get stock quote.
    else:
        return render_template('quote.html')


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == 'POST':

        # check if user provided username as input or not
        if not request.form.get("username"):
            return apology("must provide username")

        # check if user provided password as input or not
        elif not request.form.get("password"):
            return apology("must provide password")

        # If retyped password dosent match with earlier password
        if request.form.get("confirmation") != request.form.get("password"):
            return apology("Both passwords don't match")

        # search data base on the basis of username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # if username not unique then (ie more than 1 row returned) -> throw error;
        if len(rows) != 0:
            return apology("This username is already taken")

        db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", request.form.get("username"),
                   generate_password_hash(request.form.get("password")))

        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))
        session["user_id"] = rows[0]["id"]

        return redirect("/")

    if request.method == "GET":
        return render_template('register.html')
    # return apology("TODO")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    # Sell shares of stock
    if request.method == "POST":

        # check if symbol empty
        if not request.form.get("symbol"):
            return apology("must provide stock symbol")

        # check if quantity empty
        if not request.form.get("shares"):
            return apology("must provide no. of shares")

        # Store symbol & quantity
        symb = request.form.get("symbol").upper()
        qnt = float(request.form.get("shares"))

        # check if quantity non zero or float
        if qnt <= 0 or not qnt % 1 == 0:
            return apology("must provide no. of shares")

        # check if quoted quantiy available or not
        sql = db.execute("SELECT symbol, quantity FROM portfolio WHERE users_id = ? AND symbol = ?", session["user_id"], symb)

        if qnt > int(sql[0]["quantity"]):
            return apology("must provide correct no. of shares")

        # sell at current price
        look_result = lookup(symb)
        if look_result is None:
            return apology("must provide correct stock symbol")

        # Update History
        db.execute("INSERT INTO history (users_id, symbol, transactionType, marketPrice, quantity) VALUES (?, ?, ?, ?, ?)",
                   session["user_id"], symb, "sell", look_result["price"], qnt)

        # add cash
        cash = db.execute("SELECT cash FROM users WHERE id = ?;", session["user_id"])

        db.execute("UPDATE users SET cash = ? WHERE id = ?", cash[0]['cash'] + ((look_result["price"]) * qnt), session["user_id"])

        # update portfolio
        if int(qnt) == int(sql[0]["quantity"]):
            db.execute("DELETE FROM portfolio WHERE symbol = ?", symb)
        else:
            db.execute("UPDATE portfolio SET quantity = ? WHERE users_id = ? AND symbol = ? ",
                       int(sql[0]["quantity"]) - qnt, session["user_id"], symb)

        return redirect("/")

    else:
        symb = db.execute("SELECT symbol FROM portfolio WHERE users_id = ?", session["user_id"])
        return render_template("sell.html", symb=symb)
