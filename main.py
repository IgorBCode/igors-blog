from functools import wraps
from flask import Flask, render_template, redirect, url_for, request,flash, abort
from flask_bootstrap import Bootstrap5
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from flask_ckeditor import CKEditor
import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.exceptions import Forbidden
from flask_login import LoginManager, UserMixin, login_user, login_required, current_user, logout_user
from forms import CreatePostForm, RegisterUserFrom, LoginForm, CommentForm
from flask_gravatar import Gravatar
import smtplib
import os


# Initializations
app = Flask(__name__)
ckeditor = CKEditor(app)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')

# Database connection for Render.com
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')

bootstrap = Bootstrap5(app)
db = SQLAlchemy()
db.init_app(app)

##### DATABASE  TABLES ####
# User table
class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(), unique=True, nullable=False)
    name = db.Column(db.String(), nullable=False)
    password = db.Column(db.String(), nullable=False)
    # RELATIONSHIP SETTINGS
    posts = relationship('BlogPost', back_populates='author')
    comments = relationship('Comment', back_populates='comment_author')

# Blog table
class BlogPost(db.Model):
    __tablename__ = 'blog_posts'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(), unique=True, nullable=False)
    subtitle = db.Column(db.String(), nullable=False)
    date = db.Column(db.String(), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(), nullable=False)
    # RELATIONSHIP SETTINGS
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    author = relationship('User', back_populates='posts')
    comments = relationship('Comment', back_populates='parent_post')

# Comment table
class Comment(db.Model):
    __tablename__ = 'comments'
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    # RELATIONSHIP SETTINGS
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    post_id = db.Column(db.Integer, db.ForeignKey('blog_posts.id'))
    comment_author = relationship('User', back_populates='comments')
    parent_post = relationship('BlogPost', back_populates='comments')


# FLASK LOGIN MANAGER
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# GRAVATAR  SETTINGS (This gives users avatars)
gravatar = Gravatar(
    app,
    size=100,
    rating='g',
    default='retro',
    force_default=False,
    force_lower=False,
    use_ssl=False,
    base_url=None)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

@app.errorhandler(Forbidden)
def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.id != 1:
            return abort(403)
        else:
            return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def get_all_posts():
    posts = db.session.query(BlogPost).all()
    return render_template('index.html', all_posts=posts)

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterUserFrom()

    if form.validate_on_submit():
        # CHECK IF USER EXISTS
        if db.session.query(User).filter_by(email=request.form.get('email')).first():
            flash('You are already registered, please log in.')
            return redirect(url_for('login'))
        else:
            new_user = User(
                email=request.form.get('email'),
                name=request.form.get('name'),
                password=generate_password_hash(request.form.get('password'), method='pbkdf2:sha256', salt_length=8)
            )

            with app.app_context():
                db.session.add(new_user)
                db.session.commit()

            flash('Account created, please log in.')
            return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = db.session.query(User).filter_by(email=request.form.get('email')).first()
        if user:
            if check_password_hash(user.password, request.form.get('password')):
                login_user(user)
                return redirect(url_for('get_all_posts'))
            else:
                flash('Incorrect password. Please try again.')
        else:
            flash('No account with those credentials found.')
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def log_out():
    logout_user()
    return redirect(url_for('get_all_posts'))

@app.route('/post/<int:post_id>', methods=['POST', 'GET'])
def show_post(post_id):
    requested_post = db.session.query(BlogPost).get(post_id)

    comment = CommentForm()
    if comment.validate_on_submit():
        if current_user.is_authenticated:
            new_comment = Comment(
            text=request.form['comment'],
            comment_author=current_user,
            parent_post=requested_post
            )
            db.session.add(new_comment)
            db.session.commit()

        else:
            flash('Please log in to comment.')

    comment.comment.data = ""
    comments = db.session.query(Comment).all()
    return render_template('post.html', post=requested_post, form=comment, comment_list=comments)


@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/new-post', methods=['POST', 'GET'])
@admin_only
def add_post():
    post_form = CreatePostForm()
    date = datetime.datetime.now().strftime('%B %d, %Y')

    if post_form.validate_on_submit():
        new_post = BlogPost(
            title=request.form['title'],
            subtitle=request.form['subtitle'],
            date=date,
            body=request.form['body'],
            author=current_user,
            img_url=request.form['img_url'],
        )

        with app.app_context():
            db.session.add(new_post)
            db.session.commit()
        return redirect(url_for('get_all_posts'))

    return render_template('make-post.html', form=post_form)


@app.route('/edit-post/<int:post_id>', methods=['POST', 'GET'])
@admin_only
def edit_post(post_id):
    # post_to_edit = db.session.query(BlogPost).get(post_id)
    post_to_edit = requested_post = db.session.get(BlogPost, int(post_id))

    # EDIT FORM
    form = CreatePostForm(request.form, body=post_to_edit.body,
                          title=post_to_edit.title,
                          subtitle=post_to_edit.subtitle,
                          author=post_to_edit.author,
                          img_url=post_to_edit.img_url)

    if form.validate_on_submit():
        db.session.query(BlogPost).filter(BlogPost.id == post_id).update({
            "title": request.form['title'],
            "subtitle": request.form['subtitle'],
            "body": request.form['body'],
            "author": request.form['author'],
            "img_url": request.form['img_url']
        })
        db.session.commit()
        return redirect(url_for('show_post', index=post_id))

    return render_template('make-post.html', edit=True, form=form)

@app.route('/delete/<int:post_id>')
@admin_only
def delete_post(post_id):
    post_to_delete = db.get_or_404(BlogPost, post_id)
    db.session.delete(post_to_delete)
    db.session.commit()

    return redirect(url_for('get_all_posts'))

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.get('name')
        email = request.get('email')
        phone = request.get('phone')
        message = phone = request.get('message')
        send_email(data["name"], data["email"], data["phone"], data["message"])
        return redirect(url_for('contact', email_set=True))
        # return render_template('contact.html', email_sent=True)
    return render_template('contact.html', email_sent=False)

def send_email(name, email, phone, message):
    email_msg = f"Subject: New Message\n\nName: {name}\nEmail: {email}\nPhone: {phone}\nMessage: {message}"
    with smtplib.SMTP("smtp.gmail.com") as connection:
        connection.starttls()
        connection.login(os.environ.get('EMAIL_ADDY'), os.environ.get('EMAIL_PASS'))
        connection.sendmail(os.environ.get('EMAIL_ADDY'), os.environ.get('EMAIL_ADDY'), email_msg)

if __name__ == "__main__":
    app.run()
