from flask import Flask, render_template, redirect, url_for, flash, abort
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Table, Column, Integer, ForeignKey
from sqlalchemy.orm import relationship
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm
from flask_gravatar import Gravatar
import os


app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY")


#to enable ckeditor for create posts etc
ckeditor = CKEditor(app)
Bootstrap(app)

# to enable login capabilities
login_manager = LoginManager()
login_manager.init_app(app)


gravatar = Gravatar(app,
                    size=100,
                    rating='g',
                    default='retro',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)

##CONNECT TO DB
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///blog.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


##CONFIGURE TABLES

class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)

    # create Foreign Key, "user.id" the user refers to the tablename of User
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    # create reference to the User object (child), the 'blogposts' refers to the blogposts property in the User class
    author = relationship("User", back_populates="blogposts")
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)
    # create relationship to Comment
    comments = relationship("Comment", back_populates="blogpost")

class User(UserMixin, db.Model):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(250), unique=True, nullable=False)
    password = db.Column(db.String(250), nullable=False)
    name = db.Column(db.String(250), nullable=False)
    # this will act like a list of BlogPost objects attached to the each User
    # 'author' refers to the author property in BlogPost
    blogposts = relationship("BlogPost", back_populates="author")
    # add relationship to Comment
    comments = relationship("Comment", back_populates="comment_author")


class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    # create author_id in Comment table
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    # add relationship to User
    comment_author = relationship("User", back_populates="comments")
    text = db.Column(db.Text, nullable=False)
    # create blogpost_id in Comment table
    blogpost_id = db.Column(db.Integer, db.ForeignKey('blog_posts.id'))
    # add relationship to BlogPost
    blogpost = relationship("BlogPost", back_populates="comments")


db.create_all()


#admin_only decorator
def admin_only(f):
    def decorated_function(*args, **kwargs):
        if current_user.id != 1:
            return abort(403)
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__  # add this code if you want to apply decorator to multiple functions
    return decorated_function

@app.route('/')
def get_all_posts():
    posts = BlogPost.query.all()
    return render_template("index.html", all_posts=posts, logged_in=current_user.is_authenticated)


@app.route('/register', methods=["GET", "POST"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        new_user = User()
        new_user.email = form.email.data
        if User.query.filter_by(email=new_user.email).first():
            flash("You are already registered. Please log in")
            return redirect(url_for('login'))
        else:
            unhashed_password = form.password.data
            new_user.password = generate_password_hash(unhashed_password, method='pbkdf2:sha256', salt_length=8)
            new_user.name = form.name.data
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user)
            return redirect(url_for('get_all_posts', logged_in=True))
    else:
        return render_template("register.html", form=form, logged_in=current_user.is_authenticated)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route('/login', methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        login_email = form.email.data
        login_password = form.password.data
        try:
            user = User.query.filter_by(email=login_email).first()
            if check_password_hash(user.password, login_password):
                login_user(user)
                return redirect(url_for('get_all_posts', logged_in=True))
            else:
                flash("Invalid password, please try again")
                return redirect(url_for('login'))
        except AttributeError:
            flash('No such email exists, please try again')
            return redirect(url_for('login'))
    else:
        return render_template("login.html", form=form, logged_in=current_user.is_authenticated)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def show_post(post_id):
    requested_post = BlogPost.query.get(post_id)
    form = CommentForm()
    if form.validate_on_submit():
        if current_user.is_authenticated:
            new_comment = Comment(
                text=form.body.data,
                comment_author=current_user,
                # use comment_author instead of author_id to add to table Comment
                blogpost=requested_post,
                # use blogpost instead of blogpost_id to add to table Comment
            )
            db.session.add(new_comment)
            db.session.commit()
        else:
            flash("You have to be logged in to leave a comment. Please log in")
            return redirect(url_for("login"))
    return render_template("post.html", post=requested_post, form=form, logged_in=current_user.is_authenticated)


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


@app.route("/new-post", methods=["GET", "POST"])
@login_required
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author_id=current_user.id,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form, logged_in=True)


@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@login_required
@admin_only
def edit_post(post_id):
    post = BlogPost.query.get(post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author.name,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author.name = edit_form.author.data
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))

    return render_template("make-post.html", form=edit_form, logged_in=True)


@app.route("/delete/<int:post_id>")
@login_required
@admin_only
def delete_post(post_id):
    post_to_delete = BlogPost.query.get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts', logged_in=True))


if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)
