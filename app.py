from flask import Flask, request, jsonify, render_template, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
import boto3
import os
import uuid
from datetime import datetime

app = Flask(__name__)

# MySQL Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:root123@127.0.0.1/social_app_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# S3 configuration (LocalStack endpoint)
s3_client = boto3.client(
    's3',
    endpoint_url='http://localhost:4566',
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID', 'fakeAccessKey'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY', 'fakeSecretKey'),
    region_name='us-east-1'
)
bucket_name = "media-bucket"

# Ensure the bucket exists
s3_client.create_bucket(Bucket=bucket_name)

# Define Models
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    posts = db.relationship('Post', backref='author', lazy=True)
    likes = db.relationship('Like', backref='user', lazy=True)
    comments = db.relationship('Comment', backref='user', lazy=True)

class Post(db.Model):
    __tablename__ = 'posts'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    media_url = db.Column(db.String(255))  # Link to media in S3
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    likes = db.relationship('Like', backref='post', lazy=True)
    comments = db.relationship('Comment', backref='post', lazy=True)

class Like(db.Model):
    __tablename__ = 'likes'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=False)

class Comment(db.Model):
    __tablename__ = 'comments'
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=False)

# Route to Create a New Post
@app.route('/upload', methods=['POST'])
def upload():
    file = request.files['file']
    title = request.form.get('title', 'Untitled Post')
    content = request.form.get('content', '')
    user_id = request.form.get('user_id')

    # Upload file to S3
    file_name = f"{uuid.uuid4()}_{file.filename}"
    s3_client.upload_fileobj(file, bucket_name, file_name)
    media_url = f"http://localhost:4566/{bucket_name}/{file_name}"

    # Save post to database
    new_post = Post(title=title, content=content, media_url=media_url, user_id=user_id)
    db.session.add(new_post)
    db.session.commit()

    return redirect(url_for('home'))

# Route to Get a Specific Post by ID
@app.route('/post', methods=['GET'])
def get_post():
    post_id = request.args.get('post_id')
    if post_id:
        post = Post.query.get(post_id)
        if post:
            return jsonify({
                'id': post.id,
                'title': post.title,
                'content': post.content,
                'media_url': post.media_url,
                'created_at': post.created_at,
                'author': post.author.username
            })
        else:
            return jsonify({"error": "Post not found"}), 404
    return jsonify({"error": "Post ID is required"}), 400

# Route to Get All Posts by User ID
@app.route('/user/posts', methods=['GET'])
def get_posts_by_user():
    user_id = request.args.get('user_id')
    posts = Post.query.filter_by(user_id=user_id).all()
    result = []
    for post in posts:
        result.append({
            'id': post.id,
            'title': post.title,
            'content': post.content,
            'media_url': post.media_url,
            'created_at': post.created_at,
            'author': post.author.username
        })
    return jsonify(result)

# Route to Get All Posts
@app.route('/posts', methods=['GET'])
def get_all_posts():
    posts = Post.query.all()
    result = []
    for post in posts:
        result.append({
            'id': post.id,
            'title': post.title,
            'content': post.content,
            'media_url': post.media_url,
            'created_at': post.created_at,
            'author': post.author.username
        })
    return jsonify(result)

# Route to Delete a Post by ID
@app.route('/post/delete', methods=['POST'])
def delete_post():
    post_id = request.form.get('post_id')
    post = Post.query.get(post_id)
    if post:
        db.session.delete(post)
        db.session.commit()
        return jsonify({"message": "Post deleted successfully"})
    return jsonify({"error": "Post not found"}), 404

# Route to Get a Specific User by ID
@app.route('/user', methods=['GET'])
def get_user():
    user_id = request.args.get('user_id')
    user = User.query.get(user_id)
    if user:
        return jsonify({
            'id': user.id,
            'username': user.username,
            'email': user.email
        })
    return jsonify({"error": "User not found"}), 404

# Route to Get All Users
@app.route('/users', methods=['GET'])
def get_all_users():
    users = User.query.all()
    result = []
    for user in users:
        result.append({
            'id': user.id,
            'username': user.username,
            'email': user.email
        })
    return jsonify(result)

@app.route('/create_user', methods=['POST', 'GET'])
def create_user():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        # Validate input and create user
        new_user = User(username=username, email=email)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('home'))  # or any other route you want to redirect to
    return render_template('create_user.html')  # Form page to create a new user


@app.route('/')
def home():
    users = User.query.all()
    return render_template('index.html', users=users)

# Run Application
if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Creates tables in MySQL
    app.run(debug=True)
