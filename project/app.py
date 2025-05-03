import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session,jsonify
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
app.config["SECRET_KEY"] = os.urandom(24)
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

@app.route("/", methods=["GET"])
@login_required
def index():
    user_id = session["user_id"]
    holdings = db.execute("SELECT symbol, SUM(shares) AS shares, price, SUM(total) AS total FROM tracking WHERE id = :user_id GROUP BY symbol", user_id=user_id)
    cash_result = db.execute("SELECT cash FROM users WHERE id = :user_id", user_id=user_id)
    cash = cash_result[0]["cash"] if cash_result else 0
    return render_template("layout.html", holdings=holdings, cash=cash)

@app.route("/goal", methods=["GET","POST"])
@login_required
def goal():
    error = None
    amount = 0
    interest = 0
    if request.method =="POST":
        cash_result = db.execute("SELECT cash FROM users WHERE id = :user_id",user_id = session["user_id"])
        cash = int(cash_result[0]["cash"])
        target = request.form.get("goal")
        year = request.form.get("years")
        if not target or not target.isdigit() or int(target) < cash:
            error="Please fill in a valid target"
            return render_template("goal.html", error=error)
        if not year or not year.isdigit() or int(year) < 1:
            error="Please fill in a valid number of years"
            return render_template("goal.html", error= error)
        targets = int(target)
        years = int(year)
        amount = round((targets - cash)/(years * 12),3)
        interest = round((amount* 12/cash) * 100,2)
    return render_template("goal.html", amount = amount, interest = interest)


@app.route("/homepage",methods =["GET"])
@login_required
def homepage():
    user_id = session["user_id"]
    user = db.execute("SELECT username FROM users WHERE id = :user_id", user_id=user_id)
    username = user[0]["username"] if user else "Guest"
    cash_result = db.execute("SELECT cash FROM users WHERE id = :user_id", user_id=user_id)
    cash = cash_result[0]["cash"] if cash_result else 0
  # holdings = db.execute("SELECT symbol, SUM(shares) AS shares, price, SUM(total) AS total FROM tracking WHERE id = :user_id GROUP BY symbol", user_id=user_id)
    holdings = db.execute("SELECT symbol, shares, price, total FROM tracking WHERE id = :user_id ORDER BY timestamp DESC LIMIT 3 ", user_id=session["user_id"])
    #share_count = holdings[0]["shares"]
   # total = holdings[0]["price"]
   # for i in holdings:
    #    if holdings[i]["shares"] > 0:
      #      if holdings[i+1] != None:
       #         if holdings[i]["symbol"] == holdings[i+1]["symbol"]:
       #             share_count = share_count +holdings[i+1]["shares"]
        #            total = total + holdings[i+1]["price"]
    return render_template("Homepage.html", username = username, cash= cash, holdings = holdings)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    error = None
    if request.method == "POST":
        # Get the form inputs
        symbol = request.form.get("symbol").upper()
        shares = request.form.get("shares")

        # Validate stock symbol
        stock = lookup(symbol)
        if not symbol or not stock:
            error = "Invalid stock symbol"
            return render_template("buy.html",error=error )

        # Validate shares
        if not shares.isdigit() or int(shares) <= 0:
            error = "Invalid number of shares"
            return render_template("buy.html",error=error )
        shares = int(shares)

        # Get the stock's current price
        price = stock["price"]
        total_cost = price * shares

        # Check the user's available cash
        user_id = session["user_id"]
        cash_result = db.execute("SELECT cash FROM users WHERE id = :user_id", user_id=user_id)
        cash = cash_result[0]["cash"] if cash_result else 0

        if total_cost > cash:
            error ="Not enough cash"
            return render_template("buy.html",error=error )
        # Record the purchase in the "transactions" table
        db.execute(
            "INSERT INTO tracking (id, symbol, shares, price, total) VALUES (:id, :symbol, :shares, :price, :total)",
            id=user_id, symbol=symbol, shares=shares, price=price, total=total_cost
        )

        # Deduct the cost from the user's cash balance
        db.execute("UPDATE users SET cash = cash - :total_cost WHERE id = :user_id", total_cost=total_cost, user_id=user_id)
        holdings = db.execute("SELECT symbol, shares, price, total FROM tracking WHERE id = :user_id", user_id=session["user_id"])
        # Redirect to the home page
        return render_template("Homepage.html", holdings = holdings)

    else:
        # Render the buy page
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    user_id = session["user_id"]

    transactions = db.execute("SELECT symbol, shares, price, total, timestamp FROM tracking WHERE id = :user_id", user_id=user_id)
    return render_template("history.html", transactions=transactions)

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""
    error = None
    session.clear()

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if not username:
            error = "Please provide username"
            return render_template("login.html", error=error)

        if not password:
            error = "Please provide Password"
            return render_template("login.html", error=error)

        rows = db.execute("SELECT * FROM users WHERE username = ?", username)

        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], password):
            error = "invalid username and/or password"
            return render_template("login.html", error=error)

        session["user_id"] = rows[0]["id"]

        return redirect("/homepage")

    return render_template("login.html", error =error)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    error = None
    if request.method == "POST":
        symbol = request.form.get("symbol")
        stock = lookup(symbol)

        if stock is None:
            error ="Please input a symbol"
            return render_template("quote.html",error=error)

        if not stock:
            error = "Invalid Stock symbol"
            return render_template("quote.html",error=error)


        # Wrap the single dictionary in a list for consistent rendering
        return render_template("quote.html", stock=stock)

    return render_template("quote.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    error = None
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")
        rows = db.execute("SELECT * FROM users WHERE username = ?", username)
        if rows:
            error = "Username is taken. Please try another."
            return render_template("register.html",error = error)

        if not username:
            error = "Please enter a Username"
            return render_template("register.html",error = error)

        if not password:
            error = "Please enter a password"
            return render_template("register.html",error = error)

        if password != confirmation:
            error = "Passwords do not match"
            return render_template("register.html",error = error)

        hash_pw = generate_password_hash(password)
        db.execute("INSERT INTO users (username, hash, cash) VALUES (?, ?, 10000.00)", username, hash_pw)

        return redirect("/login")

    return render_template("register.html",error = error)

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    error = None
    symbols = db.execute("SELECT symbol,shares,price FROM tracking WHERE id = :user_id ", user_id=session["user_id"])
    reflect = []
    track = []
    update = []
    for symbol in symbols:
        if symbol["shares"] >0:
            reflect.append(symbol)

    if request.method == "POST":
        for index,info in enumerate(reflect):
            symbol = info["symbol"]
            shares = int(request.form.get(f"shares_{index +1}"))
            track.append(shares)
            if shares >0:
                stock = lookup(symbol)
                if set(track) == {0}:
                    error = "Please Choose your quantity before submitting"
                    return render_template("sell.html", symbols=symbols,reflect = reflect, error=error)

                if not symbol or not stock:
                    error = "Invalid stock symbol"
                    return render_template("sell.html", symbols=symbols,reflect = reflect, error=error)

               # if  int(shares) <= 0:
               #     return apology("Invalid number of shares")

                shares = int(shares)
                user_shares_result = db.execute("SELECT SUM(shares) as total FROM tracking WHERE id = :user_id AND symbol= :symbol AND price = :price ", user_id=session["user_id"],symbol=symbol, price = info["price"])
                user_shares = user_shares_result[0]["total"] if user_shares_result else 0
                #return str(user_shares)
                if not user_shares or shares > user_shares:
                    error = "Not enough shares"
                    return render_template("sell.html", symbols=symbols,reflect = reflect, error=error)

                price = stock["price"]
                total_value = shares * price

                #db.execute("UPDATE tracking SET shares = shares -:shares WHERE id = :user_id AND symbol= :symbol AND price = :price ", shares = shares,user_id=session["user_id"],symbol=symbol, price = info["price"])

                db.execute("INSERT INTO tracking (id, symbol, shares, price, total) VALUES (:id, :symbol,:shares, :price, :total)",
                   id=session["user_id"], symbol=symbol, shares=-shares, price=price, total=-total_value)
                db.execute("UPDATE users SET cash = cash + :value WHERE id = :user_id", value=total_value, user_id=session["user_id"])
                #db.execute("UPDATE users SET shares = :shares WHERE id = :user_id AND symbol= :symbol AND price ")
                #updated = db.execute("SELECT shares FROM tracking WHERE id = :user_id AND symbol = :symbol AND price =:price ", user_id=session["user_id"], symbol=symbol, price = info["price"])
                #if updated == 0:
                #     db.execute("DELETE FROM tracking WHERE id = :user_id AND symbol = :symbol AND price =:price ", user_id=session["user_id"], symbol=symbol, price = info["price"])
        return redirect("/homepage")
    for symbol in reflect:
        if symbol["shares"] >0:
            update.append(symbol)
    return render_template("sell.html", symbols=symbols,update = update)
