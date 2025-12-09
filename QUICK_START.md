# Quick Start Guide

## Running the Database Initialization

### If you have MySQL installed locally (or XAMPP):

1. **Make sure MySQL is running**
   - Check Windows Services
   - Or if using XAMPP: Start MySQL from XAMPP Control Panel

2. **Create a database** (if not already created):
   ```sql
   CREATE DATABASE mystory CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   ```
   Or via command line:
   ```bash
   mysql -u root -p -e "CREATE DATABASE mystory CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
   ```

3. **Create a `.env` file** in the project root:
   ```env
   DATABASE_URL=mysql://root:your_password@localhost:3306/mystory
   ```
   Or use individual components:
   ```env
   DB_HOST=localhost
   DB_PORT=3306
   DB_NAME=mystory
   DB_USER=root
   DB_PASSWORD=your_password
   ```

4. **Run the initialization script**:
   ```bash
   python init_db.py
   ```

### If you're using Render:

1. **Create a MySQL database** on Render
2. **The `DATABASE_URL` is automatically provided** by Render
3. **The app will auto-initialize** on first startup, OR run:
   ```bash
   python init_db.py
   ```

### If you don't have MySQL:

**No problem!** The app will work without a database:
- Storylines will load from config files
- Books will still be generated
- Logs will go to console only

You can add the database later when you're ready.

## Running the Application

1. **Install dependencies** (if not already done):
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up your `.env` file** with at minimum:
   ```env
   OPENAI_API_KEY=sk-your-key-here
   ```

3. **Run the Flask app**:
   ```bash
   flask run
   ```
   Or:
   ```bash
   python app.py
   ```

4. **Open your browser** to: http://127.0.0.1:5000

## Troubleshooting

### Database Connection Errors
- Make sure MySQL is running (check Windows Services or XAMPP Control Panel)
- Check your `.env` file has correct database credentials
- Verify the database exists: `mysql -u root -p -e "SHOW DATABASES;"`
- For XAMPP users: Default port is 3306, user is usually `root` with empty password

### Missing Dependencies
- Run: `pip install -r requirements.txt`

### OpenAI API Errors
- Make sure `OPENAI_API_KEY` is set in `.env`
- Check your API key is valid and has credits

