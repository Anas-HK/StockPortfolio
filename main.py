# To run flask in production mode, give following commands in powershell:
#$env:FLASK_APP="flask_project.py"
#$env:FLASK_ENV="development"
#flask run

import os
import requests
from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
# testing
#import sqlite3

from LookupHelper import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///mysite/finance.db")

# Make sure API key is set
#API_KEY = "pk_c9a992e212984b8ab67ef632cca42c3d"
#if not os.environ.get(API_KEY):
#    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks Index has no method"""


    data = db.execute("SELECT symbol, companyName, stock_price, shares, total_price FROM stock_info WHERE user_id==:session GROUP by symbol", session=session["user_id"])
    # In the below variable, the total amount of cash plus stock price will be stored
    grand_total = 0

        # Since cash is in another table, we will run another query to get cash value.
    cash = db.execute("SELECT cash FROM users WHERE id==:session", session=session["user_id"])
    cash = cash[0]
    cash = cash["cash"]

    grand_total += cash

        # If the data list of dicts is not empty then only we shall update the view table.
    if data != []:
            # data has been returned a list of dicts having index of 0, to add the values we can either ues the for loop or do data[0]["shares"]
        for row in data:

            shares = row["shares"]
            total_price = row["total_price"]
            symbol = row["symbol"]
            companyName = row["companyName"]
            stock_price = row["stock_price"]
            grand_total += row["total_price"]

            check = db.execute("SELECT * FROM view WHERE user_id==:session AND symbol==:symbol", session=session["user_id"], symbol=symbol)

            # If the check row is empty then we shall insert new row.
            if check == []:

                db.execute("INSERT INTO view (user_id, symbol, companName, stock_price, shares, total_price, cash) VALUES (?, ?, ?, ?, ?, ?, ?)",
                session["user_id"], symbol, companyName, usd(stock_price), shares, usd(total_price), cash)

            else:
                db.execute("UPDATE view SET shares=:shares, total_price=:total_price WHERE user_id==:session AND symbol==:symbol",
                shares=shares, total_price=usd(total_price), session=session["user_id"], symbol=symbol)


    # Now after updating the view table we will just assign the list of dicts to the "stocks" variable and render that variable to our html file and plug in the values.
    stocks = db.execute("SELECT symbol, companName, stock_price, shares, total_price, cash From view WHERE user_id==:session GROUP BY symbol", session=session["user_id"])

    # 11/11/21
    return render_template("index.html", stocks=stocks, grand_total=usd(grand_total), cash=usd(cash))

# Update 11/11/21 I'm using this code for deploying application to production
if __name__ == "__main__":
    from waitress import serve
    serve(app, host="0.0.0.0", port=8080)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buying stocks"""
    if request.method == "POST":

        if not request.form.get("symbol"):
            flash("Symbol must be provided")
            return render_template("buy.html")

        if not request.form.get("shares"):
            flash("Number of shares missing")
            return render_template("buy.html")

        # Symbol needs to be uppercase for comparision.
        symbol=request.form.get("symbol").upper()

        stocks = lookup(symbol)
        # Now the variable stock will have a dictionary of all the info of the stocks
        if stocks is None:
            flash("Incorrect Symbol")
            return render_template("buy.html")

        # The form returns a numerical value, which means it's a string and in order to do calculations with it, we have to convert it to float or int.
        shares = int(request.form.get("shares"))
        stock_price = stocks["price"]

        # Calculating total price of the stocks the user wants to buy to check if he has enough cash.
        total_price = stock_price * float(shares)

        # It is imp to note that db.execute returns a list of dicts.
        # To find information about the current user, we will find it's row in the database using the session id.
        # Where :session_id is a placeholder and it's value is assigned after the comma.
        cash_list = db.execute("SELECT cash FROM users WHERE id == :session_id", session_id=session["user_id"])

        # To assign value from a list of dict to a variable we will first convert the list of dict into a dictionary
        cash_list = cash_list[0]
        # Then we will assign the value of the key we want to use
        cash = cash_list["cash"]
        cash = cash - total_price
        # Below we are allowing only 2 digits to appear after the decimal point.
        cash = round(cash, 2)
        # Now we'll check if the user has enough cash to buy the stocks
        if cash < 0:
            flash("You don't have enough cash.")
            return render_template("buy.html")
        # If the user has enough cash then we will update the database.
        # NOTE: Instead of adding data to our buy table, we are directly updating our stock_info table.

        # Checking if a row exist in our table
        check = db.execute("SELECT * FROM stock_info WHERE user_id==:session AND symbol==:symbol", session=session["user_id"], symbol=symbol)

        # Inserting stock info in our history table
        db.execute("INSERT INTO history (user_id, symbol, shares, stock_price, time) VALUES (?, ?, ?, ?, datetime('now', 'localtime'))", session["user_id"], symbol, shares, stocks["price"])

        # If the row is empty than we shall insert new row in the table
        if check == []:

            db.execute("INSERT INTO stock_info (user_id, symbol, companyName, stock_price, shares, total_price, cash) VALUES (?, ?, ?, ?, ?, ?, ?)",
            session["user_id"], symbol, stocks["name"], stocks["price"], shares, round(total_price, 2), cash)


        else:
            # Since we need to update our row, we will have to add the previous stock values to our new ones
            for row in check:
                shares+=row["shares"]
                total_price+=row["total_price"]


            db.execute("UPDATE stock_info SET shares=:shares, total_price=:ttl_price WHERE user_id==:session AND symbol==:symbol",
            shares=shares, ttl_price=round(total_price, 2), session=session["user_id"], symbol=symbol)

        # We only need to update total cash in our user table because it is linked to the buy table.
        # We'll only update that users cash which was buying the stocks.
        db.execute("UPDATE users SET cash=:cash WHERE id==:session_id", cash=cash, session_id=session["user_id"])

        flash("Bought!")
        return redirect("/")


    else:
        return render_template("buy.html")

@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    # In history we just need to retrieve data from query and render it in our history template
    # If we use datetime function in select then the time would get updated, we don't want that since we have already updated that in the INSERT queries.
    history=db.execute("SELECT symbol, shares, stock_price, time FROM history WHERE user_id==:session", session=session["user_id"])

    # Adding dollar sign to stock price
    for row in history:
        row["stock_price"] = usd(row["stock_price"])

    return render_template("history.html", stocks=history)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            # Below we are using the flash function to display alert.
            flash("Username must be provided")
            return render_template("login.html")

        # Ensure password was submitted
        elif not request.form.get("password"):
            flash("Password must be provided")
            return render_template("login.html")

        # Query database for username
        # Where :username is a placeholder and its value is plugged by getting it from the form.
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct. The length of row must be one because the username needs to be unique
        # check_power_hash() is a function that turns the password into a hashcode using it's algorithm which is a combination of the password and the key.
        # It will also check if the password submitted in the form is valid or not by comparing it with the hash column.
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            flash("Invalid Username or Password")
            return render_template("login.html")

        # Remember which user has logged in
        # Each session is gonna be unique because the id is unique per person.
        # We're using sessions because we want to make the user's interaction with the website local. So that other users don't affect a different user and vice versa.
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        flash("Logged In")
        return redirect("/")


    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()
    flash("Logged out successfully")
    # Redirect user to login form
    return render_template("login.html")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":

        # Checking symbol field is not empty
        if not request.form.get("symbol"):
            flash("Symbol is missing")
            return render_template("quote.html")

        # Getting the symbol. Converting it into uppercase because if user inputs the symbol as lowercase
        symbol=request.form.get("symbol")
        # Assigning the list of key value pairs of the stock
        stocks = lookup(symbol)
        # Need to ensure that the stock symbol is valid. If the symbol is incorrect, than the lookup function will return None type.
        if stocks is None:
            flash("Incorrect Symbol")
            return render_template("quote.html")

        # After getting the stock information we will redirect to a new page and plug in the stock info.
        return render_template("quoteprice.html", name=stocks["name"], price=usd(stocks["price"]), symbol=stocks["symbol"])

    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    if request.method == "POST":
        # Ensuring user submits username and password
        # We are checking if the username field in the form is blank or not
        if not request.form.get("username"):
            flash("Uername must be provided")
            return render_template("register.html")

        if not request.form.get("password"):
            flash("Password must be provided")
            return render_template("register.html")

        # Need to validate that the password is confirmed
        if request.form.get("password") != request.form.get("confirmPswd"):
            flash("Password doesn't match")
            return render_template("register.html")

        # First we'll confirm that the username is unique and not already selected.
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))
        # Now if there is no matching name for our username then it is confirmed that the name is unique
        # Note that the SELECT query returns an empty list if no data is matched with the query. Where [] represents an empty list.
        if rows != []:
            flash("Username already taken")
            return render_template("register.html")

        else:
        # Now since the username and password has been validated, we will put it in the database.
        # To secure the users password we will hash the password using a function from werkzeug.security so that the orignal password will not be stored
        # but a scrambled version of the password will be stored on the database
            db.execute("INSERT INTO users (username, hash) VALUES( ?, ?)" , request.form.get("username"), generate_password_hash(request.form.get("password")))

        flash("Registered!")
        return redirect("/login")

    else:
        return render_template("register.html")

# Need to redo sell funciton
@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    # Below we are querying the symbol of the stocks the user has bought to be displayed on the dropdown list on sell.html
    symb = db.execute("SELECT symbol FROM stock_info WHERE user_id==:session", session=session["user_id"])

    if request.method == "POST":

        # Checking if the form is not empty
        if not request.form.get("symbol"):
            flash("No symbol selected")
            return redirect("/sell")

        if not request.form.get("shares"):
            flash("No shares selected")
            #return render_template("sell.html")
            return redirect("/sell")

        # Getting the symbol and the shares the user selected in the form.
        symbol = request.form.get("symbol")
        shares = int(request.form.get("shares"))

        stock = lookup(symbol)

        # In this query we are getting the amount of shares of the stock the user wants to sell.
        user = db.execute("SELECT shares, total_price FROM stock_info WHERE user_id==:session AND symbol==:symbol", session=session["user_id"], symbol=symbol)

        # Below we are checking if the user has the amount of shares he wants to sale
        # The [0] in user[0]["shares"] means that it is the first and only row in the list of dict.
        if not shares <= user[0]["shares"]:
            flash("You don't have enough shares")
            return redirect("/sell")

        # Below we are subtracting the amount of shares the user wants to sell from the total shares of the stock
        upd_shares=user[0]["shares"] - shares
        # We also need to update total_price of the updated shares
        upd_total_price = upd_shares * stock["price"]

        # Below is the amount we need to add in cash
        cash_added = shares * stock["price"]

        # We need to show sold shares in our history table as negative.
        history_shares = shares * -1
        # Inserting row in our history table
        # The datetime funtion will convert UTC time to local machine time.
        db.execute("INSERT INTO history (user_id, symbol, shares, stock_price, time) VALUES (?, ?, ?, ?, datetime('now', 'localtime'))", session["user_id"], symbol, history_shares, stock["price"])

        # If the updated amount of shares is 0, then it means that the user has sold all the stocks and we shall remove it from the table.
        if upd_shares==0:
            db.execute("DELETE FROM stock_info WHERE user_id==:session AND symbol==:symbol",
            session=session["user_id"], symbol=symbol)
            # We also need to delete from the view table because it wont be affected unless it is deleted.
            db.execute("DELETE FROM view WHERE user_id==:session AND symbol==:symbol",
            session=session["user_id"], symbol=symbol)

        else:

            # If the data needs to be updated then we need to add the new values to the existing ones. Shares has already been updated
            db.execute("UPDATE stock_info SET shares=:shares, total_price=:total_price WHERE user_id==:session AND symbol==:symbol"
            , shares=upd_shares, total_price=round(upd_total_price,2), session=session["user_id"], symbol=symbol)

        cash = db.execute("SELECT cash FROM users WHERE id==:session", session=session["user_id"])

        upd_cash = cash_added + cash[0]["cash"]

        # We also need to add the cash gotten from selling the stocks.
        db.execute("UPDATE users SET cash=:cash WHERE id==:session", cash=upd_cash ,session=session["user_id"])
        flash("Sold!")
        return redirect("/")

    else:
        return render_template("sell.html", stock=symb)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
