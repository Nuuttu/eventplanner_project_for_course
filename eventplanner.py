from flask import Flask, render_template, redirect, flash, session, abort, request
from flask_sqlalchemy import SQLAlchemy 
from flask_wtf import FlaskForm
from wtforms.ext.sqlalchemy.orm import model_form
from werkzeug.security import generate_password_hash, check_password_hash
from wtforms import StringField, PasswordField, validators, SubmitField
from datetime import datetime

app = Flask(__name__)
app.secret_key="cvhQr6otEqweccwejf8O8YdSO6U7liDu6ycoz"
app.config["SQLALCHEMY_DATABASE_URI"]='postgresql:///tuomo' # change "tuomo" to "own database"
db = SQLAlchemy(app)

class Room(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, unique=True, nullable=False)
    owner = db.Column(db.Integer, foreign_key=True, nullable=False)

class RoomForm(FlaskForm):
    name = StringField("Create an Event: ", validators=[validators.InputRequired()])

class Users(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String, nullable=False, unique=True)
    passwordHash = db.Column(db.String, nullable=False)

    def setPassword(self, password):
        self.passwordHash = generate_password_hash(password)

    def checkPassword(self, password):
        return check_password_hash(self.passwordHash, password)


class UsersForm(FlaskForm):
    username = StringField("Username", validators=[validators.InputRequired()])
    password = PasswordField("Password", validators=[validators.InputRequired()])

class RegisterForm(FlaskForm):
    username = StringField("Username", validators=[validators.InputRequired()])
    password = PasswordField("Password", validators=[validators.InputRequired()])
    registerKey = StringField("Registration Key", validators=[validators.InputRequired()])


class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    task = db.Column(db.String, nullable=False)
    c_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    userId = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    user = db.relationship('Users', backref=db.backref('tasks', lazy=True))

    roomId = db.Column(db.Integer, db.ForeignKey('room.id'), nullable=True)
    room = db.relationship('Room', backref=db.backref('tasks', lazy=True))

TaskForm = model_form(Task, base_class=FlaskForm, db_session=db.session, exclude = ["userId", "roomId", "c_date", "room", "user"])


class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String, nullable=False)

    ownerId = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    owner = db.relationship('Users', backref=db.backref('comments', lazy=True))

    roomId = db.Column(db.Integer, db.ForeignKey('room.id'), nullable=True)
    room = db.relationship('Room', backref=db.backref('comments', lazy=True))

CommentForm = model_form(Comment, base_class=FlaskForm, db_session=db.session, exclude = ["ownerId", "owner", "roomId", "room"])

## CurrentUsers config

def currentUser():
    try:
        uid = int(session["uid"])
    except:
        return None
    return Users.query.get(uid)

app.jinja_env.globals["currentUser"] = currentUser

def loggedIn():
    if not currentUser():
        return abort(403)

def currentRoom():
    try:
        rid = int(session["rid"])
    except:
        return None
    return Room.query.get(rid)

app.jinja_env.globals["currentRoom"] = currentRoom


## user view

@app.route("/register", methods=["GET", "POST"])
def registerUsers():
    form = RegisterForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        registerKey = form.registerKey.data

        if Users.query.filter_by(username=username).first():
            flash("Users already exist. Log in")
            return redirect("/login")
        if not registerKey == "cube":
            flash("Wrong register key. You need to know this in order to register.")
            return redirect("/register")
        user = Users(username=username)
        user.setPassword(password)

        db.session.add(user)
        db.session.commit()
        
        flash("added a account. now login")
        return redirect("/login")
        
    return render_template("register.html", form=form)


@app.route("/login", methods=["GET", "POST"])
def loginUsers():
    form = UsersForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        
        user = Users.query.filter_by(username=username).first()
        if not user:
            flash("Login failed.")
            return redirect("/login")
        if not user.checkPassword(password):
            flash("Login failed.")
            return redirect("/login")
        
        session["uid"]=user.id
        flash("Login success. Hello " + currentUser().username)
        return redirect("/")
        
    return render_template("login.html", form=form)


@app.route("/logout")
def logoutUsers():
    session["uid"] = None
    session["rid"] = None
    flash("Logged out. See you soon :)")
    return redirect("/")



## Before First Request

@app.before_first_request
def initDb():
    db.create_all()
    db.session.commit()


## Main view

@app.route("/")
def base():
    helloMessage = "Hello, please login or register for Eventplanner!"
    if currentUser():
        tasks = Task.query.filter_by(userId=currentUser().id)
        if Task.query.filter_by(userId=currentUser().id).count() == 0:
            return render_template("index.html")
        else:
            return render_template("index.html", tasks=tasks)
    return render_template("index.html")


@app.route("/eventview", methods=["GET", "POST"])
def eventView():
    loggedIn()
    tasks = Task.query.filter_by(roomId=currentRoom().id)
    comments = Comment.query.filter_by(roomId=currentRoom().id)
    comment = Comment()
    form = CommentForm()
    if not currentRoom():
        abort(403)
    if form.validate_on_submit():
        form.populate_obj(comment)
        comment.ownerId = currentUser().id
        comment.roomId = currentRoom().id
        db.session.add(comment)
        db.session.commit()
        return redirect("/eventview")
    if Task.query.filter_by(roomId=currentRoom().id).count() == 0:
        return render_template("eventview.html", comments=comments, form=form)
    else:
        return render_template("eventview.html", tasks=tasks, comments=comments, form=form)
    

@app.errorhandler(404)
def custom404(e):
    return render_template("404.html")

@app.errorhandler(403)
def custom403(e):
    flash("You need to log in to do this.")
    if currentRoom():
        return redirect("/eventview")
    return redirect("/")


@app.route("/rooms", methods=["GET", "POST"])
def rooms(ID=None):
    loggedIn()
    room = Room()
    form = RoomForm()
    if form.validate_on_submit():
        form.populate_obj(room)
        room.owner = currentUser().id
        if Room.query.filter_by(name=room.name).first():
            flash("Event already created. Use different name or join excisting.")
            return redirect("/rooms")
        db.session.add(room)
        db.session.commit()
    if "joinroom" in request.form:
        if not Room.query.filter_by(name=request.form["joinroom"]).first():
            flash("Can't find that event")
            return redirect("/rooms")
        roomname = request.form["joinroom"]
        room = Room.query.filter_by(name=roomname).first()
        roomtojoin = "/joinroom/" + str(room.id)
        return redirect(roomtojoin)
    rooms = Room.query.filter_by(owner=currentUser().id)
    if Room.query.filter_by(owner=currentUser().id).count() == 0:
        return render_template("rooms.html", form=form)
    return render_template("rooms.html", rooms=rooms, form=form)

@app.route("/joinroom/<int:id>", methods=["GET", "POST"])
def joinRoom(id):
    loggedIn()
    session["rid"]=id
    flash("Join event success. You are now in: " + currentRoom().name)
    return redirect("/eventview")

@app.route("/leaveroom")
def leaveRoom():
    session["rid"] = None
    flash("Left event view.")
    return redirect("/")

@app.route("/rooms/delete/<int:id>")
def deleteRoom(id):
    loggedIn()
    room = Room.query.get_or_404(id)
    if currentUser().id != room.owner:
        abort(403)    
    return render_template("deleteroom.html", room=room)
    

@app.route("/rooms/remove/<int:id>")
def removeRoom(id):
    loggedIn()
    room = Room.query.get_or_404(id)
    if currentUser().id != room.owner:
        abort(403)
    db.session.delete(room)
    db.session.commit()
    flash("Deleted event")
    return redirect("/rooms")


@app.route("/task/<int:id>/edit", methods=["GET", "POST"])
@app.route("/task/add", methods=["GET", "POST"])
def addTask(id=None):
    if not currentUser():
        abort(403)
    task = Task()
    task.userId = currentUser().id
    if currentRoom():
        task.roomId = currentRoom().id
    message = "Add a new Task"
    flashmessage = "Added Task: "
    pageTitle = "Add Task"
    if id:
        task = Task.query.get_or_404(id)
        if currentUser().id != task.userId:
            abort(403)  
        message = "Edit Task: " + task.task
        flashmessage = "Edited " + task.task  +" -> "
        pageTitle = "Edit Task"
    form = TaskForm(obj=task)
    if form.validate_on_submit():
        form.populate_obj(task)
        db.session.add(task)
        db.session.commit()
        flash(flashmessage + task.task)
        if currentRoom():
            return redirect("/eventview")
        return redirect("/")
    return render_template("add.html", form=form, pageTitle=pageTitle)

@app.route("/task/<int:id>/delete")
def deleteTask(id):
    loggedIn()
    task = Task.query.get_or_404(id)
    if currentUser().id == task.userId:
        return render_template("delete.html", task=task)
    if currentUser().id == currentRoom().owner and task.roomId == currentRoom().id:
        return render_template("delete.html", task=task)
    abort(403)
    
    

@app.route("/<int:id>/annihilate")
def annihilateTask(id):
    loggedIn()
    task = Task.query.get_or_404(id)
    if currentUser().id == task.userId:
        db.session.delete(task)
        db.session.commit()
        flash("Deleted task: - " + task.task)
        if currentRoom():
            return redirect("/eventview")
        return redirect("/")
    if currentUser().id == currentRoom().owner and task.roomId == currentRoom().id:
        db.session.delete(task)
        db.session.commit()
        flash("Deleted task: - " + task.task)
        if currentRoom():
            return redirect("/eventview")
        return redirect("/")
    abort(403)

@app.route("/comment/delete/<int:id>")
def deleteComment(id):
    comment = Comment.query.get(id)
    if comment.owner.id == currentUser().id:
        db.session.delete(comment)
        db.session.commit()
        flash("Deleted comment")
        return redirect("/eventview")
    if currentUser().id == currentRoom().owner and comment.roomId == currentRoom().id:
        db.session.delete(comment)
        db.session.commit()
        flash("Deleted comment")
        return redirect("/eventview")
    abort(403)
    
if __name__ == "__main__":
    app.run(debug=True)
