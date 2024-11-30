
# Create database for user account and saved story 
import sqlite3

def init_db():
    conn = sqlite3.connect('story_generator.db')
    cursor = conn.cursor()
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    )''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS stories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        story TEXT,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )''')
    conn.commit()
    conn.close()

init_db()



#All functions for generating story and user account creations.
from flask import Flask, render_template, request, session
from transformers import GPT2LMHeadModel, GPT2Tokenizer
import torch

from werkzeug.security import generate_password_hash, check_password_hash
from flask import redirect, url_for, flash


from flask import make_response


app = Flask(__name__)
app.secret_key = "some_secret_key"  


model_name = "gpt2" 
model = GPT2LMHeadModel.from_pretrained(model_name)
tokenizer = GPT2Tokenizer.from_pretrained(model_name)


@app.route('/')
def home():
    return render_template('index.html')


def retrieve_related_stories(genre, character):
    conn = sqlite3.connect('story_generator.db')
    cursor = conn.cursor()
    cursor.execute("SELECT story FROM stories WHERE story LIKE ?", ('%' + genre + '%',))
    related_stories = cursor.fetchall()
    conn.close()
    return related_stories



@app.route('/generate_story', methods=['POST'])
def generate_story():
    genre = request.form['genre']
    character = request.form['character']
    setting = request.form.get('setting', 'urban')  

    # Retrieve related stories
    related_stories = retrieve_related_stories(genre, character)
    related_story_text = " ".join([story[0] for story in related_stories])  # Combine all related stories

    prompt = (
        f"Write a {genre} story like novel. "
        f"The main character, {character}, is in a setting described as {setting}. "
        f"Here are some previous stories that might help guide the writing: {related_story_text} "
        "Write with rich descriptions, atmospheric details, and realistic dialogue. "
        "Use the style of a novel, with paragraph breaks, inner thoughts, and interactions. "
    )

    inputs = tokenizer.encode(prompt, return_tensors="pt")

    outputs = model.generate(
        inputs,
        max_length=1000,  
        num_return_sequences=1,
        no_repeat_ngram_size=2,
        temperature=0.85,  
        top_k=50,
        top_p=0.9,
        pad_token_id=tokenizer.eos_token_id
    )

    story = tokenizer.decode(outputs[0], skip_special_tokens=True)


    session['story'] = story

    return render_template('story.html', story=story)



@app.route('/continue_story', methods=['POST'])
def continue_story():
    
    previous_story = session.get('story', '')


    prompt = (
    f"Continue the story in a novel-like style. "
    f"The story so far: {previous_story}\n\n"
    "Focus on the main character, and develop the scene with realistic dialogue, "
    "inner thoughts, and vivid descriptions. Highlight their emotions, interactions with others, "
    "and progress the story forward with a clear direction."
)


    
    inputs = tokenizer.encode(prompt, return_tensors="pt")

    
    outputs = model.generate(
        inputs,
        max_length=1000,  
        num_return_sequences=1,
        no_repeat_ngram_size=2,
        temperature=0.85,
        top_k=50,
        top_p=0.9,
        pad_token_id=tokenizer.eos_token_id
    )

    
    continuation = tokenizer.decode(outputs[0], skip_special_tokens=True)
    full_story = previous_story + "\n\n" + continuation  

    session['story'] = full_story  

    return render_template('story.html', story=full_story)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = sqlite3.connect('story_generator.db')
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        conn.close()
        
        if not user:
            flash("Username not found.", "error")
            return redirect(url_for('login'))
        elif not check_password_hash(user[2], password):
            flash("Incorrect password.", "error")
            return redirect(url_for('login'))
        else:
            session['user_id'] = user[0]
            flash("Login successful!", "success")
            return redirect(url_for('home'))
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])
        
        conn = sqlite3.connect('story_generator.db')
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
            conn.commit()
        except sqlite3.IntegrityError:
            flash("Username already exists.", "error")
            return redirect(url_for('register'))
        finally:
            conn.close()
        
        flash("Registration successful! Please log in.", "success")
        return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/profile')
def profile():
    user_id = session.get('user_id')
    if not user_id:
        flash("Please log in to view your profile.", "error")
        return redirect(url_for('login'))

    conn = sqlite3.connect('story_generator.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, story FROM stories WHERE user_id = ?", (user_id,))
    stories = cursor.fetchall()  
    conn.close()

    return render_template('profile.html', stories=stories)



@app.route('/download_story', methods=['GET'])
def download_story():
    story = session.get('story', 'No story available to download.')
    response = make_response(story)
    response.headers['Content-Disposition'] = 'attachment; filename=story.txt'
    response.mimetype = 'text/plain'
    return response

@app.route('/save_story', methods=['POST'])
def save_story():
    user_id = session.get('user_id')
    story = session.get('story')
    if user_id and story:
        conn = sqlite3.connect('story_generator.db')
        cursor = conn.cursor()
        cursor.execute("INSERT INTO stories (user_id, story) VALUES (?, ?)", (user_id, story))
        conn.commit()
        conn.close()
        flash('Story saved successfully!', 'success')
    else:
        flash('Failed to save story. Please log in.', 'error')
    return redirect(url_for('profile'))  


@app.route('/download_story/<int:story_id>')
def download_saved_story(story_id):
    user_id = session.get('user_id')
    if not user_id:
        flash("Please log in to download stories.", "error")
        return redirect(url_for('login'))

    conn = sqlite3.connect('story_generator.db')
    cursor = conn.cursor()
    cursor.execute("SELECT story FROM stories WHERE id = ? AND user_id = ?", (story_id, user_id))
    story = cursor.fetchone()
    conn.close()

    if story:
        response = make_response(story[0])
        response.headers['Content-Disposition'] = f'attachment; filename=story_{story_id}.txt'
        response.mimetype = 'text/plain'
        return response
    else:
        flash("Story not found or you don't have permission to download it.", "error")
        return redirect(url_for('profile'))

@app.route('/delete_story/<int:story_id>', methods=['POST', 'GET'])
def delete_saved_story(story_id):
    user_id = session.get('user_id')
    if not user_id:
        flash("Please log in to delete stories.", "error")
        return redirect(url_for('login'))

    conn = sqlite3.connect('story_generator.db')
    cursor = conn.cursor()
    

    cursor.execute("SELECT id FROM stories WHERE id = ? AND user_id = ?", (story_id, user_id))
    story = cursor.fetchone()
    
    if story:
        cursor.execute("DELETE FROM stories WHERE id = ?", (story_id,))
        conn.commit()
        flash(f"Story {story_id} has been deleted.", "success")
    else:
        flash("Story not found or you don't have permission to delete it.", "error")
    
    conn.close()
    return redirect(url_for('profile'))



@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for('home'))




if __name__ == '__main__':
    app.run(debug=True)




