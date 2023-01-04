import os
from flask import Flask, flash, request, redirect, url_for, render_template, send_from_directory, session
from werkzeug.utils import secure_filename
import dxfchecker
from io import StringIO
import sys
from uuid import uuid4

UPLOAD_FOLDER = './uploads'
ALLOWED_EXTENSIONS = {'dxf'}

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.secret_key = "BLAHBLAHBLAH"

print("__name__ = " + __name__)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def set_session_uuid():
    uuid = str(uuid4())
    session['UUID'] = uuid
    return uuid


@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        # check if the post request has the file part
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['file']
        # If the user does not select a file, the browser submits an
        # empty file without a filename.
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)

            if 'UUID' not in session.keys():
                set_session_uuid()

            path = os.path.join(app.config['UPLOAD_FOLDER'], session['UUID'])

            if not os.path.exists(path):
                os.makedirs(path)

            file.save(os.path.join(path, filename))
            #return redirect(url_for('download_file', name=filename))
            old_stdout = sys.stdout
            sys.stdout = mystdout = StringIO()
            dxfchecker.check(os.path.join(path, filename))
            sys.stdout = old_stdout

            # cleanup
            os.remove(os.path.join(path, filename))
            os.rmdir(path)

            return render_template('uploadfile.html', output = mystdout.getvalue())
        else:
            return redirect(request.url)
    else:
        return render_template('uploadfile.html')

@app.route('/uploads/<name>')
def download_file(name):
    return send_from_directory(app.config["UPLOAD_FOLDER"], name)

if __name__ == '__main__':
    app.run()  # run our Flask app