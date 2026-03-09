# EduMind LMS - Deployment Guide

## Deployment Options

### Option 1: Render (Recommended - Free Tier Available)

#### Quick Deploy Steps:
1. Go to [render.com](https://render.com) and create an account
2. Connect your GitHub repository
3. Create a new Web Service:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app --bind 0.0.0.0:$PORT`
   - **Runtime**: Python 3.11

#### Environment Variables (in Render Dashboard):
| Variable | Value |
|----------|-------|
| SECRET_KEY | Generate a secure random string |
| DATABASE_PATH | /app/edumind.db |
| UPLOAD_FOLDER | /app/static/uploads |
| DEBUG | False |

#### Or use render.yaml (Automatic Deployment):
Simply push to GitHub with `render.yaml` in your repository and Render will auto-detect and deploy.

---

### Option 2: PythonAnywhere

#### Setup Steps:
1. Create account at [pythonanywhere.com](https://www.pythonanywhere.com)
2. Upload files using Files tab or git clone
3. Create virtual environment:
   ```bash
   mkvirtualenv edumind --python=python3.11
   pip install -r requirements.txt
   ```
4. Configure Web app:
   - Go to Web tab → Add new web app
   - Select Manual configuration → Python 3.11
   - Edit WSGI to point to `wsgi.py`

#### Environment Variables:
| Variable | Value |
|----------|-------|
| SECRET_KEY | your-secure-random-string |
| DATABASE_PATH | /home/yourusername/edumind/edumind.db |
| UPLOAD_FOLDER | /home/yourusername/edumind/static/uploads |
| DEBUG | False |

---

## Files Required for Deployment

```
app.py
requirements.txt
runtime.txt
Procfile
render.yaml (for Render)
wsgi.py (for PythonAnywhere)
templates/
static/
```

## After Deployment

1. Visit your app URL
2. The database will be created automatically on first run
3. You may need to seed initial data using the seed scripts

## Troubleshooting

### 500 Error on Render
- Check build logs in Render dashboard
- Ensure all dependencies are in requirements.txt

### Static Files Not Loading
- Ensure static folder is in correct location
- Check that UPLOAD_FOLDER path is correct

### Database Issues
- Ensure DATABASE_PATH is set correctly
- Check that the app has write permissions
