from flask import Flask, redirect
from auth.routes import auth_bp
from child.routes import child_bp
from uploadPost.routes import upload_bp
from parent.routes import parent_bp
from flask import send_from_directory
from quiz.routes import quiz_bp
from auth.api import api_bp
from parent.api import parent_api_bp
from childMessage.routes import child_message_bp


from flask_cors import CORS
app = Flask(__name__)
CORS(
    app,
    supports_credentials=True
)

app.secret_key = "littlenet_secret_key"

app.register_blueprint(auth_bp)
app.register_blueprint(child_bp)
app.register_blueprint(upload_bp)
app.register_blueprint(parent_bp)
app.register_blueprint(quiz_bp)
app.register_blueprint(api_bp)
app.register_blueprint(parent_api_bp)
app.register_blueprint(child_message_bp)


print(app.url_map)

@app.route("/")
def home():
    return redirect("/login/")



@app.route("/uploads/<path:filename>")
def uploaded_file(filename):

    return send_from_directory(
        "uploads",
        filename
    )




    
if __name__ == "__main__":
    app.run(debug=True)